"""Usage:
  python -m jobradar          collect, score and rebuild docs/
  python -m jobradar check    test each company feed once and print what works
  python -m jobradar --offline  skip the web; only rescore pasted jobs in inbox/
"""
import datetime as dt
import json
import os
import sys
from pathlib import Path

from . import notify, report, sources, store
from .score import build_skill_finder, score

ROOT = Path(__file__).resolve().parent.parent


def load(name):
    return json.loads((ROOT / "config" / name).read_text(encoding="utf-8"))


def main(argv):
    profile, comp, skills = load("profile.json"), load("companies.json"), load("skills.json")["skills"]
    targets = list(profile["target_titles"])
    # a one-off keyword search (Actions > daily-run > Run workflow) widens this run only
    extra = [k.strip().lower() for k in os.environ.get("EXTRA_TITLES", "").split(",") if k.strip()]
    targets += extra
    comp["workday_search_terms"] = comp["workday_search_terms"] + extra
    find = build_skill_finder(skills)
    today = dt.date.today().isoformat()
    (ROOT / "data").mkdir(exist_ok=True)
    db = store.connect(ROOT / "data" / "jobs.sqlite")

    # monthly-discovered companies: one broad "Malaysia" search each, to keep the daily run short
    disc = ROOT / "config" / "discovered.json"
    if disc.exists():
        comp["companies"] += [{**c, "terms": [""]} for c in json.loads(disc.read_text(encoding="utf-8"))["companies"]]

    jobs = []
    if "--offline" not in argv:
        for c in comp["companies"]:
            try:
                got = sources.COLLECTORS[c["ats"]](c, targets, comp["workday_search_terms"])
                store.log_run(db, today, c["ats"], c["name"], True, len(got), sources.NOTES.pop(c["ats"], ""))
                jobs += got
                print(f"ok    {c['name']:<28} {len(got)} jobs")
            except sources.Skip as e:
                print(f"skip  {c['name']:<28} {e}")
            except Exception as e:  # one broken feed must not stop the run
                store.log_run(db, today, c["ats"], c["name"], False, 0, repr(e))
                print(f"FAIL  {c['name']:<28} {e!r}")
    if "check" in argv:
        db.commit()
        return
    jobs += sources.inbox(ROOT / "inbox", ROOT / "data" / "pasted.jsonl")

    for j in jobs:
        store.upsert(db, j, score(j, profile, find(j["title"] + "\n" + j["description"])), today)
    db.commit()

    since = (dt.date.today() - dt.timedelta(days=3)).isoformat()
    # rescore open jobs too, so a change to profile.json applies to every job, not just new ones
    for j in store.active_jobs(db, since):
        store.upsert(db, j, score(j, profile, find(j["title"] + "\n" + j["description"])), j["last_seen"])
    db.commit()
    active = store.active_jobs(db, since)
    runs = [dict(r) for r in db.execute(  # latest result per source today
        "SELECT * FROM runs WHERE rowid IN (SELECT max(rowid) FROM runs WHERE run_date = ? GROUP BY company)", (today,))]
    closed = store.closed_jobs(db, since, (dt.date.today() - dt.timedelta(days=45)).isoformat())
    posts = store.post_counts(db)
    cv = load("cv.sample.json")  # the public page only ever carries the sample; real CVs stay in the browser
    # cv.locked.json = your own CV encrypted with the key in your private link; safe to publish
    locked = load("cv.locked.json") if (ROOT / "config" / "cv.locked.json").exists() else None
    report.build(ROOT / "docs", active, runs, profile, today, closed, posts, cv, skills, locked)
    if "--offline" not in argv:
        notify.send_new_matches(db, active, today, profile)
    print(f"{len(jobs)} collected today, {len(active)} active, report in docs/index.html")


if __name__ == "__main__":
    main(sys.argv[1:])
