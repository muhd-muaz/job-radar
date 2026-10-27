"""Match score (0-100) of a job against the profile, plus skills found in the ad."""
import re

# job tracks for the radar's slices; first match wins, so the specific ones come first
TRACKS = [
    ("Data engineering", ("data engineer", "analytics engineer", "etl", "data pipeline", "data platform", "data warehouse",
                          "data integration", "big data", "database", "sql developer", "data architect")),
    ("BI and reporting", ("bi ", "bi developer", "bi analyst", "business intelligence", "power bi", "reporting", "mis ",
                          "dashboard", "visuali")),
    ("Data science", ("data scientist", "machine learning", "ml ", "ai engineer")),
    ("Data analysis", ("data analyst", "analytics", "insight", "data quality", "data governance", "product analyst", "data")),
    ("Business and systems", ("business analyst", "systems analyst", "system analyst", "process analyst", "it analyst",
                              "erp", "sap", "application support", "rpa", "digital transformation", "analyst")),
]


def track(title):
    t = title.lower() + " "
    return next((name for name, keys in TRACKS if any(k in t for k in keys)), "Other")


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


def score(job, profile, found):
    title = job["title"].lower()
    title_pts = max((w for k, w in profile["target_titles"].items() if k in title), default=0)
    have = profile["have_skills"]
    asked = found - {"mandarin", "bahasa malaysia"}
    matched = sorted(s for s in asked if s in have)
    missing = sorted(s for s in asked if s not in have)
    learning = set(profile.get("learning_skills", []))
    # skills I'm actively learning count as half a gap, so data-engineering ads aren't buried
    gap = sum(1 if s in learning and profile.get("learning_counts_half") else 2 for s in missing)
    skill_fit = sum(have[s] for s in matched) / max(1, sum(have[s] for s in matched) + gap)
    skill_fit *= 0.6 + 0.4 * min(1, len(matched) / 4)  # an ad naming only 1-2 skills is weak evidence
    seniority = max((p for k, p in profile["seniority_penalty"].items() if k in title), default=0)
    yrs = [int(n) for n in re.findall(r"(\d{1,2})\s*\+?\s*(?:-\s*\d+\s*)?years?", job["description"].lower()) if int(n) < 20]
    if yrs and min(yrs) >= 5:
        seniority += 15
    desc = job["description"].lower()
    language = max((p for lang, p in profile.get("language_penalty", {}).items() if lang in title or lang in desc), default=0)
    # full-time, fresh grad to mid level: push contract / part-time roles down, lift entry-level ones
    job_type = max((p for k, p in profile.get("job_type_penalty", {}).items() if k in title), default=0) or \
        max((p for k, p in profile.get("job_type_penalty", {}).items() if k in desc[:600]), default=0) // 2
    level = max((b for k, b in profile.get("level_bonus", {}).items() if k in title or k in desc), default=0)
    loc = job.get("location", "").lower()
    bonus = profile.get("location_bonus", {})
    place = 0
    if any(w in loc for w in profile.get("preferred_locations", [])):
        place = bonus.get("preferred", 0)
    elif any(w in loc for w in ("penang", "pulau pinang", "johor", "kedah", "kulim", "melaka", "sabah", "sarawak", "ipoh", "perak")):
        place = bonus.get("elsewhere_in_malaysia", 0)
    penalty = seniority + language + job_type - level - place
    # not full-time, or an internship: never a strong fit
    cap = 45 if any(k in title for k in list(profile.get("job_type_penalty", {})) + ["intern"]) else 100
    # the title decides the track: no target title, or an off-track one (finance, sales...), caps the score
    if not title_pts:
        cap = min(cap, 50)
    if any(k in title for k in profile.get("off_track_titles", [])) and title_pts < 3:
        cap = min(cap, 50)
    pts = title_pts / 3 * 45 + skill_fit * 55 - penalty
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
    on_track = title_pts >= 2 and not any(k in title for k in profile.get("off_track_titles", []))
    # a senior role in my track: worth a polite note asking about junior openings in the same team
    reach_out = on_track and seniority >= 20 and not any(k in title for k in ("intern", "trainee"))
    return {
        "score": max(0, min(cap, round(pts))),
        "parts": parts, "track": track(job["title"]), "reach_out": reach_out,
        "matched": matched, "missing": missing,
        "learning": sorted(s for s in missing if s in profile.get("learning_skills", [])),
        "projects": projects,
    }
