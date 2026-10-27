"""Usage:
  python -m jobradar          collect, score and rebuild docs/
  python -m jobradar check    test each company feed once and print what works
  python -m jobradar --offline  skip the web; only rescore pasted jobs in inbox/
"""
import datetime as dt
import json
import sys
from pathlib import Path

from . import report, sources, store
from .score import build_skill_finder, score

ROOT = Path(__file__).resolve().parent.parent


def load(name):
    return json.loads((ROOT / "config" / name).read_text(encoding="utf-8"))


def main(argv):
    profile, comp, skills = load("profile.json"), load("companies.json"), load("skills.json")["skills"]
    targets = list(profile["target_titles"])
    find = build_skill_finder(skills)
    today = dt.date.today().isoformat()
    (ROOT / "data").mkdir(exist_ok=True)
    db = store.connect(ROOT / "data" / "jobs.sqlite")

    jobs = []
    if "--offline" not in argv:
        for c in comp["companies"]:
            try:
                got = sources.COLLECTORS[c["ats"]](c, targets, comp["workday_search_terms"])
                store.log_run(db, today, c["ats"], c["name"], True, len(got))
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
    active = store.active_jobs(db, since)
    runs = [dict(r) for r in db.execute("SELECT * FROM runs WHERE run_date = ?", (today,))]
    report.build(ROOT / "docs", active, runs, profile, today)
    print(f"{len(jobs)} collected today, {len(active)} active, report in docs/index.html")


if __name__ == "__main__":
    main(sys.argv[1:])
