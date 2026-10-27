"""Match score (0-100) of a job against the profile, plus skills found in the ad."""
import re


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
    skill_fit = sum(have[s] for s in matched) / max(1, sum(have[s] for s in matched) + 2 * len(missing))
    penalty = max((p for k, p in profile["seniority_penalty"].items() if k in title), default=0)
    yrs = [int(n) for n in re.findall(r"(\d{1,2})\s*\+?\s*(?:-\s*\d+\s*)?years?", job["description"].lower()) if int(n) < 20]
    if yrs and min(yrs) >= 5:
        penalty += 15
    loc = job.get("location", "").lower()
    bonus = profile.get("location_bonus", {})
    if any(w in loc for w in profile.get("preferred_locations", [])):
        penalty -= bonus.get("preferred", 0)
    elif any(w in loc for w in ("penang", "pulau pinang", "johor", "kedah", "kulim", "melaka", "sabah", "sarawak", "ipoh", "perak")):
        penalty -= bonus.get("elsewhere_in_malaysia", 0)
    pts = title_pts / 3 * 45 + skill_fit * 55 - penalty
    projects = [p["name"] for p in profile["projects"] if set(p["skills"]) & set(matched)]
    return {
        "score": max(0, min(100, round(pts))),
        "matched": matched, "missing": missing,
        "learning": sorted(s for s in missing if s in profile.get("learning_skills", [])),
        "projects": projects,
    }
