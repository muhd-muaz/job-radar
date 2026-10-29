"""Writes docs/index.html (the shortlist page) and docs/jobs.json.
The page is one static file: job data is embedded as JSON and rendered in the browser."""
import json
import re
from collections import Counter
from pathlib import Path

TEMPLATE = Path(__file__).with_name("page.html")


SALARY = re.compile(r"(?:RM|MYR)\s?(\d[\d,.]*)\s*(k)?\s*(?:-|–|to)\s*(?:RM|MYR)?\s?(\d[\d,.]*)\s*(k)?", re.I)


def salary(text):
    """'RM 4,000 - RM 6,000' -> 'RM 4,000 – 6,000' (monthly figures only; yearly ranges are skipped)."""
    for m in SALARY.finditer(text or ""):
        lo, hi = (float(v.replace(",", "")) * (1000 if k else 1) for v, k in ((m.group(1), m.group(2)), (m.group(3), m.group(4))))
        if 1000 <= lo <= hi <= 50000:
            return f"RM {lo:,.0f} – {hi:,.0f}"
    return ""


def slim(j, posts):
    out = {k: j[k] for k in ("id", "company", "title", "location", "url", "source", "score",
                             "first_seen", "last_seen", "matched", "missing", "learning", "projects")}
    out["salary"] = salary(j.get("description"))
    out.update({k: j.get(k) for k in ("parts", "track", "reach_out")})
    out["posts"] = posts.get((j["company"].lower(), j["title"].strip().lower()), 1)
    return out


def build(outdir, active, runs, profile, today, closed=(), posts=None, cv=None):
    posts = posts or {}
    outdir.mkdir(exist_ok=True)
    jobs, shown = [], set()
    for j in active:
        key = (j["company"].lower(), j["title"].strip().lower())
        if key in shown:  # same role posted twice
            continue
        shown.add(key)
        jobs.append(slim(j, posts))
    gaps = Counter(s for j in jobs for s in j["missing"]).most_common(15)
    data = {
        "today": today, "jobs": jobs, "gaps": gaps,
        "closed": [slim(j, posts) for j in closed],
        "learning": profile.get("learning_skills", []),
        "preferred": profile.get("preferred_locations", []),
        "projects": {p["name"]: p.get("url", "") for p in profile["projects"]},
        "have": sorted(profile["have_skills"]),
        "outreach": profile.get("outreach", {}),
        "cv": cv or {},
        "feeds": [{"name": r["company"], "ok": bool(r["ok"]), "jobs": r["jobs"], "error": r["error"]} for r in runs],
    }
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    (outdir / "index.html").write_text(TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", blob), encoding="utf-8")
    (outdir / "jobs.json").write_text(json.dumps(jobs, indent=1, ensure_ascii=False), encoding="utf-8")
