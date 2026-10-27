"""Writes docs/index.html (the shortlist page) and docs/jobs.json.
The page is one static file: job data is embedded as JSON and rendered in the browser."""
import json
from collections import Counter
from pathlib import Path

TEMPLATE = Path(__file__).with_name("page.html")


def build(outdir, active, runs, profile, today):
    outdir.mkdir(exist_ok=True)
    jobs, shown = [], set()
    for j in active:
        key = (j["company"].lower(), j["title"].strip().lower())
        if key in shown:  # same role posted twice
            continue
        shown.add(key)
        jobs.append({k: j[k] for k in ("id", "company", "title", "location", "url", "source", "score",
                                       "first_seen", "matched", "missing", "learning", "projects")})
    gaps = Counter(s for j in jobs for s in j["missing"]).most_common(15)
    data = {
        "today": today, "jobs": jobs, "gaps": gaps,
        "learning": profile.get("learning_skills", []),
        "preferred": profile.get("preferred_locations", []),
        "projects": {p["name"]: p.get("url", "") for p in profile["projects"]},
        "feeds": [{"name": r["company"], "ok": bool(r["ok"]), "jobs": r["jobs"], "error": r["error"]} for r in runs],
    }
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    (outdir / "index.html").write_text(TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", blob), encoding="utf-8")
    (outdir / "jobs.json").write_text(json.dumps(jobs, indent=1, ensure_ascii=False), encoding="utf-8")
