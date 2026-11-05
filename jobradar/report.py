import datetime as dt
"""Writes docs/index.html (the shortlist page) and docs/jobs.json.
The page is one static file: job data is embedded as JSON and rendered in the browser."""
import json
import re
from collections import Counter
from pathlib import Path
from .score import TRACKS
from .sources import alert_who_where, not_a_job, _STATES

# careers-site slugs turned into names; the real names people know
NAMES = {"bpinternational": "bp", "ocbc": "OCBC", "cw": "Cushman & Wakefield", "rbc": "RBC", "nttlimited": "NTT",
         "rytbank": "Ryt Bank", "spgi": "S&P Global", "dxctechnology": "DXC Technology", "nxp": "NXP", "airasia": "AirAsia",
         "bdx": "BD", "msd": "MSD", "aig": "AIG", "hpe": "HPE", "jci": "Johnson Controls", "propertyguru": "PropertyGuru",
         "paloaltonetworks": "Palo Alto Networks", "airliquidehr": "Air Liquide", "brooksauto": "Brooks Automation",
         "unhcr": "UNHCR", "sime": "Sime Darby", "aveva": "AVEVA"}


def tidy(company, location, source=""):
    """Older alert rows ran company, place and pay together; slugs like 'Bpinternational (bpCareers)' read badly."""
    c, loc = (company or "").strip(), (location or "").strip()
    if re.match(r"\d+ new jobs? in", c) or c.startswith("<"):   # an alert header, not a company
        c = ""
    c = re.sub(r"\s*\b(Strong applicant|Actively recruiting|Early applicant)\b", "", c)
    if (source.endswith("alert") and (not loc or re.search(r", (?:%s)$" % _STATES, c))) or " · " in c or "<" in c or " RM" in c or "Posted on" in c or re.search(r"\b(Sdn\.? ?Bhd|Berhad|Limited)\b.+", c, re.I):
        c2, place, _ = alert_who_where([re.sub(r"<.*", "", c)])
        c, loc = c2 or c, loc or place
    key = re.sub(r"\s*\(.*?\)$", "", c).lower()
    c = NAMES.get(key, c)
    if c.isupper() and len(c) > 5:
        c = c.title().replace("Sdn. Bhd.", "Sdn. Bhd.").replace("Sdn Bhd", "Sdn Bhd")
    m = re.match(r"^(?:Malaysia|MYS|MY)\s*[-–]\s*(.+)$", loc)
    if m:
        loc = m.group(1)
    if loc.isupper():
        loc = loc.title()
    return c, loc

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
    out["company"], out["location"] = tidy(j["company"], j.get("location"), j.get("source", ""))
    out["salary"] = salary(j.get("description"))
    out.update({k: j.get(k) for k in ("parts", "math", "track", "reach_out")})
    out["posts"] = posts.get((j["company"].lower(), j["title"].strip().lower()), 1)
    return out


def build(outdir, active, runs, profile, today, closed=(), posts=None, cv=None, skills=None, locked=None):
    posts = posts or {}
    outdir.mkdir(exist_ok=True)
    jobs, shown = [], set()
    for j in active:
        if not_a_job(j["title"], j.get("url", "")):   # older alert rows saved before the parser skipped these
            continue
        key = (j["company"].lower(), j["title"].strip().lower())
        if key in shown:  # same role posted twice
            continue
        shown.add(key)
        jobs.append(slim(j, posts))
    gaps = Counter(s for j in jobs for s in j["missing"]).most_common(15)
    data = {
        "today": today, "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), "jobs": jobs, "gaps": gaps,
        "closed": [slim(j, posts) for j in closed],
        "learning": profile.get("learning_skills", []),
        "preferred": profile.get("preferred_locations", []),
        "projects": {p["name"]: p.get("url", "") for p in profile["projects"]},
        "have": sorted(profile["have_skills"]),
        "outreach": profile.get("outreach", {}),
        "cv": cv or {},
        "skills": skills or {},
        "tracks": [[name, list(keys)] for name, keys in TRACKS],
        "teaser": profile.get("public_teaser", {}),
        "locked": locked or None,
        "feeds": [{"name": r["company"], "ok": bool(r["ok"]), "jobs": r["jobs"], "error": r["error"]} for r in runs],
    }
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    (outdir / "index.html").write_text(TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", blob), encoding="utf-8")
    (outdir / "jobs.json").write_text(json.dumps(jobs, indent=1, ensure_ascii=False), encoding="utf-8")
