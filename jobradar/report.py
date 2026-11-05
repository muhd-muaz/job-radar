import datetime as dt
"""Writes docs/index.html (the shortlist page) and docs/jobs.json.
The page is one static file: job data is embedded as JSON and rendered in the browser."""
import json
import re
from collections import Counter
from pathlib import Path
from .score import TRACKS, is_preferred
from .sources import alert_who_where, not_a_job, _STATES

# careers-site slugs turned into names; the real names people know
NAMES = {"bpinternational": "bp", "gehc": "GE HealthCare", "jj": "Johnson & Johnson", "wk": "Wolters Kluwer", "hlb": "Hong Leong Bank",
         "suse": "SUSE", "fico": "FICO", "lseg": "LSEG", "tsys": "TSYS", "jll": "JLL", "kla": "KLA", "erm": "ERM", "abb": "ABB", "cgg": "CGG", "cnx": "CNX", "wmg": "WMG", "us gutor": "Gutor", "sec": "SEC", "rhe": "RHE", "ag": "AG", "ext": "EXT",
         "data centers": "Data Centers", "ikano-retail": "Ikano Retail", "ocbc": "OCBC", "cw": "Cushman & Wakefield", "rbc": "RBC", "nttlimited": "NTT",
         "rytbank": "Ryt Bank", "spgi": "S&P Global", "dxctechnology": "DXC Technology", "nxp": "NXP", "airasia": "AirAsia",
         "bdx": "BD", "msd": "MSD", "aig": "AIG", "hpe": "HPE", "jci": "Johnson Controls", "propertyguru": "PropertyGuru",
         "paloaltonetworks": "Palo Alto Networks", "airliquidehr": "Air Liquide", "brooksauto": "Brooks Automation",
         "unhcr": "UNHCR", "sime": "Sime Darby", "aveva": "AVEVA"}


CITIES = {"kuala lumpur": "", "putrajaya": "", "labuan": "", "cyberjaya": "Selangor", "petaling jaya": "Selangor", "shah alam": "Selangor",
          "subang jaya": "Selangor", "puchong": "Selangor", "bandar sunway": "Selangor", "seri kembangan": "Selangor",
          "telok panglima garang": "Selangor", "setia alam": "Selangor", "ara damansara": "Selangor", "kota damansara": "Selangor",
          "klang": "Selangor", "kajang": "Selangor", "bangsar": "Kuala Lumpur", "mont kiara": "Kuala Lumpur", "bukit bintang": "Kuala Lumpur",
          "bukit jalil": "Kuala Lumpur", "cheras": "Kuala Lumpur", "johor bahru": "Johor", "iskandar puteri": "Johor", "kulai": "Johor",
          "batu kawan": "Penang", "bayan lepas": "Penang", "kulim": "Kedah", "ipoh": "Perak", "seremban": "Negeri Sembilan",
          "bandar enstek": "Negeri Sembilan", "nilai": "Negeri Sembilan", "kota kinabalu": "Sabah", "kuching": "Sarawak"}
STATES = ["Selangor", "Kuala Lumpur", "Penang", "Pulau Pinang", "Johor", "Kedah", "Perak", "Melaka", "Negeri Sembilan", "Pahang",
          "Sabah", "Sarawak", "Kelantan", "Terengganu", "Putrajaya"]


REAL_WORDS = {"Wise", "Flex", "Luno", "Citi", "Coda", "Grab", "Omya", "Visa", "Zoom", "Axi", "Sime", "Ryt", "Arm", "Dell", "Intel", "Ford", "Shell", "Agoda", "Maxis", "Celcom", "Petronas", "Lazada", "Gojek", "Monee", "Wahed", "Bosch", "Dyson", "Jabil", "Capco", "Swift", "Strada", "Ramboll", "Avnet", "Zalora", "Astro"}


def my_place(loc):
    """'MYS, Petaling Jaya (NDMY)' -> 'Petaling Jaya, Selangor'. Finds the first Malaysian town or state named; else ''."""
    low = (loc or "").lower()
    if "<" in low:
        return "Malaysia"
    hits = sorted((low.find(c), c) for c in CITIES if c in low)
    if hits:
        c = hits[0][1]
        name = "Kuala Lumpur" if c == "kuala lumpur" else c.title()
        return f"{name}, {CITIES[c]}" if CITIES[c] else name
    st = sorted((low.find(x.lower()), x) for x in STATES if x.lower() in low)
    if st:
        return "Penang" if st[0][1] == "Pulau Pinang" else st[0][1]
    return "Malaysia" if "malaysia" in low or re.search(r"\bmys?\b", low) else ""


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
    if re.fullmatch(r"[A-Z][a-z]{1,3}", c) and c not in REAL_WORDS:   # short slugs are initials: Abb -> ABB
        c = c.upper()
    if c.lower() == c and len(c) > 3:
        c = c.title()
    tidy_loc = my_place(loc)
    # the page decides "nearby" from the shown place, so only swap when that answer stays the same
    if tidy_loc and is_preferred(tidy_loc, PROFILE) == is_preferred(loc, PROFILE):
        loc = tidy_loc
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


PROFILE = {}


def build(outdir, active, runs, profile, today, closed=(), posts=None, cv=None, skills=None, locked=None):
    posts = posts or {}
    PROFILE.update(profile)
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
        "feeds": [{"name": tidy(r["company"], "")[0], "ok": bool(r["ok"]), "jobs": r["jobs"], "error": r["error"]} for r in runs],
    }
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    (outdir / "index.html").write_text(TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", blob), encoding="utf-8")
    (outdir / "jobs.json").write_text(json.dumps(jobs, indent=1, ensure_ascii=False), encoding="utf-8")
