"""Match score (0-100) of a job against the profile, plus skills found in the ad."""
import re

# job tracks for the radar's slices; first match wins, so the specific ones come first
TRACKS = [
    ("Data centre", ("data centre", "data center", "datacenter", "critical facilit", "mission critical", "dcim",
                     "dc operations")),
    ("Data engineering", ("data engineer", "analytics engineer", "etl", "data pipeline", "data platform", "data warehouse",
                          "data integration", "big data", "database", "sql developer", "data architect")),
    ("BI and reporting", ("bi ", "bi developer", "bi analyst", "business intelligence", "power bi", "reporting", "mis ",
                          "dashboard", "visuali")),
    ("Data science", ("data scientist", "machine learning", "ml ", "ai engineer")),
    ("Data analysis", ("data analyst", "analytics", "insight", "data quality", "data governance", "product analyst", "data")),
    ("Business and systems", ("business analyst", "systems analyst", "system analyst", "process analyst", "it analyst",
                              "erp", "sap", "application support", "rpa", "digital transformation", "analyst")),
]


# Keywords match whole words, plus common endings ("analyst" -> "analysts", "visuali" -> "visualisation"),
# so "intern" no longer hits "International", "erp" no longer hits "Enterprise" and "thai" no longer hits "Thailand".
_ENDINGS = r"(?:s|es|ed|er|ers|or|ors|ing|ings|ment|ments|ial|y|ry|ist|ists|ic|ics|ation|ations|[sz]ation|[sz]ations)?"
_KW = {}


def has(key, text):
    rx = _KW.get(key)
    if rx is None:
        k = key.lower()
        end = "" if not k[-1].isalnum() else _ENDINGS + r"(?![a-z0-9])"
        rx = _KW[key] = re.compile(r"(?<![a-z0-9])" + re.escape(k) + end)
    return bool(rx.search(text))


def any_has(keys, text):
    return any(has(k, text) for k in keys)


def track(title):
    t = title.lower() + " "
    return next((name for name, keys in TRACKS if any_has(keys, t)), "Other")


# a language only counts against the job when the ad asks for it, not when it names a country or a client
_ASKS = re.compile(r"proficien|fluen|speak|spoken|written|language|bilingual|read and write|command of|native")


def needs_language(lang, title, desc):
    if has(lang, title):
        return True
    for m in re.finditer(r"(?<![a-z0-9])" + re.escape(lang), desc):
        if has(lang, desc[m.start():m.start() + len(lang) + 12]) and _ASKS.search(desc[max(0, m.start() - 80):m.end() + 80]):
            return True
    return False


def _rx(term):
    return re.compile(r"(?<![a-z0-9])" + re.escape(term.strip()) + r"(?![a-z0-9])")


def build_skill_finder(skills_cfg):
    table = {}
    for skill, aliases in skills_cfg.items():
        terms = ([skill] if len(skill) > 1 else []) + aliases
        table[skill] = [_rx(t.lower()) for t in terms if t.strip()]

    def find(text):
        t = (text or "").lower()
        return {s for s, rxs in table.items() if any(r.search(t) for r in rxs)}
    return find


def is_preferred(location, profile):
    """KL/Selangor (profile.preferred_locations). The single rule for scoring and the email;
    the page's isLocal() mirrors it for ads pasted in the browser."""
    loc = (location or "").lower() + " "
    return any(w in loc for w in profile.get("preferred_locations", []))


def score(job, profile, found):
    title = job["title"].lower() + " "   # so keys like "temp " also match at the end of a title
    title_pts = max((w for k, w in profile["target_titles"].items() if has(k, title)), default=0)
    have = profile["have_skills"]
    asked = found - {"mandarin", "bahasa malaysia"}
    matched = sorted(s for s in asked if s in have)
    missing = sorted(s for s in asked if s not in have)
    learning = set(profile.get("learning_skills", []))
    # skills I'm actively learning count as half a gap, so data-engineering ads aren't buried
    gap = sum(1 if s in learning and profile.get("learning_counts_half") else 2 for s in missing)
    skill_fit = sum(have[s] for s in matched) / max(1, sum(have[s] for s in matched) + gap)
    skill_fit *= 0.6 + 0.4 * min(1, len(matched) / 4)  # an ad naming only 1-2 skills is weak evidence
    seniority = max((p for k, p in profile["seniority_penalty"].items() if has(k, title)), default=0)
    yrs = [int(n) for n in re.findall(r"(\d{1,2})\s*\+?\s*(?:-\s*\d+\s*)?years?", job["description"].lower()) if int(n) < 20]
    if yrs and min(yrs) >= 5:
        seniority += 15
    desc = job["description"].lower()
    language = max((p for lang, p in profile.get("language_penalty", {}).items() if needs_language(lang, title, desc)), default=0)
    # full-time, fresh grad to mid level: push contract / part-time roles down, lift entry-level ones
    job_type = max((p for k, p in profile.get("job_type_penalty", {}).items() if has(k, title)), default=0) or \
        max((p for k, p in profile.get("job_type_penalty", {}).items() if has(k, desc[:600])), default=0) // 2
    level = max((b for k, b in profile.get("level_bonus", {}).items() if has(k, title) or has(k, desc)), default=0)
    loc = job.get("location", "").lower()
    bonus = profile.get("location_bonus", {})
    place = 0
    if is_preferred(loc, profile):
        place = bonus.get("preferred", 0)
    elif any(w in loc for w in ("penang", "pulau pinang", "johor", "kedah", "kulim", "melaka", "sabah", "sarawak", "ipoh", "perak")):
        place = bonus.get("elsewhere_in_malaysia", 0)
    penalty = seniority + language + job_type - level - place
    # not full-time, or an internship: never a strong fit
    cap = 45 if any_has(list(profile.get("job_type_penalty", {})) + ["intern", "internship"], title) else 100
    # the title decides the track: no target title, or an off-track one (finance, sales...), caps the score
    if not title_pts:
        cap = min(cap, 50)
    if any_has(profile.get("off_track_titles", []), title) and title_pts < 3:
        cap = min(cap, 50)
    pts = round(title_pts / 3 * 45) + round(skill_fit * 55) - penalty  # rounded parts, so the page sum adds up
    projects = [p["name"] for p in profile["projects"] if set(p["skills"]) & set(matched)]
    # each part on a 0-100 scale for the page's pizza chart (100 = no problem on that front)
    parts = {
        "Job title": round(title_pts / 3 * 100),
        "Skills": round(skill_fit * 100),
        "Level": max(0, 100 - seniority * 2),
        "Entry-friendly": min(100, 50 + level * 5),
        "Full-time": max(0, 100 - job_type * 3),
        "Language": max(0, 100 - language * 4),
        "Location": 100 if place > 0 else 0 if place < 0 else 50,
    }
    on_track = title_pts >= 2 and not any_has(profile.get("off_track_titles", []), title)
    # a senior role in my track: worth a polite note asking about junior openings in the same team
    reach_out = on_track and seniority >= 20 and not any_has(("intern", "internship", "trainee"), title)
    # the sum behind the score, so the page can show it adds up
    adjust = [[k, v] for k, v in (("Junior-friendly", level), ("In KL or Selangor", place if place > 0 else 0),
              ("Outside KL and Selangor", place if place < 0 else 0), ("Senior title or 5+ years", -seniority),
              ("Needs another language", -language), ("Not permanent full-time", -job_type)) if v]
    math = {"title": round(title_pts / 3 * 45), "skills": round(skill_fit * 55), "adjust": adjust, "cap": cap}
    return {
        "score": max(0, min(cap, round(pts))),
        "parts": parts, "math": math, "track": track(job["title"]), "reach_out": reach_out,
        "matched": matched, "missing": missing,
        "learning": sorted(s for s in missing if s in profile.get("learning_skills", [])),
        "projects": projects,
    }
