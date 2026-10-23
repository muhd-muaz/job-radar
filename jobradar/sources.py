"""Collectors for public career feeds. Each returns a list of job dicts:
{id, source, company, title, location, url, posted, description}
"""
import html
import json
import re
import urllib.request
from pathlib import Path

UA = "job-radar/1.0 (personal job search; github.com/muhd-muaz/job-radar)"
MY_WORDS = ("malaysia", "kuala lumpur", "petaling jaya", "selangor", "penang", "pulau pinang",
            "cyberjaya", "putrajaya", "johor", "kulim", "kedah", "melaka", "sabah", "sarawak", "ipoh")


def http_json(url, payload=None, timeout=30):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": UA, "Accept": "application/json",
        **({"Content-Type": "application/json"} if data else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def strip_html(text):
    text = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", text or "", flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", html.unescape(text)).strip()


def in_malaysia(location):
    loc = (location or "").lower()
    return any(w in loc for w in MY_WORDS)


def title_wanted(title, targets):
    t = (title or "").lower()
    return any(k in t for k in targets)


def workday(c, targets, terms):
    base = f"https://{c['host']}/wday/cxs/{c['tenant']}/{c['site']}"
    seen, jobs = set(), []
    for term in terms:
        for offset in range(0, 100, 20):
            res = http_json(f"{base}/jobs", {"appliedFacets": {}, "limit": 20, "offset": offset,
                                             "searchText": f"{term} Malaysia"})
            posts = res.get("jobPostings", [])
            for p in posts:
                path = p.get("externalPath", "")
                if path in seen or not title_wanted(p.get("title"), targets):
                    continue
                seen.add(path)
                loc = p.get("locationsText", "")
                # "2 Locations" hides the country, so check the detail page
                if not in_malaysia(loc) and "location" not in loc.lower():
                    continue
                info = http_json(f"{base}{path}").get("jobPostingInfo", {})
                loc = ", ".join(filter(None, [info.get("location")] + (info.get("additionalLocations") or [])))
                if not in_malaysia(loc):
                    continue
                jobs.append({
                    "id": f"wd:{c['tenant']}:{info.get('jobReqId') or path}",
                    "source": "workday", "company": c["name"], "title": info.get("title") or p["title"],
                    "location": loc, "url": info.get("externalUrl") or f"https://{c['host']}/{c['site']}{path}",
                    "posted": info.get("startDate", ""), "description": strip_html(info.get("jobDescription")),
                })
            if len(posts) < 20:
                break
    return jobs


def greenhouse(c, targets, terms):
    res = http_json(f"https://boards-api.greenhouse.io/v1/boards/{c['slug']}/jobs?content=true")
    return [{
        "id": f"gh:{c['slug']}:{j['id']}", "source": "greenhouse", "company": c["name"],
        "title": j["title"], "location": (j.get("location") or {}).get("name", ""),
        "url": j.get("absolute_url", ""), "posted": (j.get("updated_at") or "")[:10],
        "description": strip_html(html.unescape(j.get("content", ""))),
    } for j in res.get("jobs", [])
        if title_wanted(j["title"], targets) and in_malaysia((j.get("location") or {}).get("name"))]


def lever(c, targets, terms):
    res = http_json(f"https://api.lever.co/v0/postings/{c['slug']}?mode=json")
    out = []
    for j in res:
        loc = ", ".join((j.get("categories") or {}).get("allLocations") or [(j.get("categories") or {}).get("location", "")])
        if title_wanted(j.get("text"), targets) and in_malaysia(loc):
            out.append({
                "id": f"lv:{c['slug']}:{j['id']}", "source": "lever", "company": c["name"],
                "title": j["text"], "location": loc, "url": j.get("hostedUrl", ""),
                "posted": "", "description": j.get("descriptionPlain", "") + "\n" + " ".join(
                    strip_html(l.get("content", "")) for l in j.get("lists", [])),
            })
    return out


def smartrecruiters(c, targets, terms):
    base = f"https://api.smartrecruiters.com/v1/companies/{c['slug']}/postings"
    res = http_json(f"{base}?country=my&limit=100")
    out = []
    for j in res.get("content", []):
        if not title_wanted(j.get("name"), targets):
            continue
        d = http_json(f"{base}/{j['id']}")
        sections = (d.get("jobAd") or {}).get("sections") or {}
        loc = j.get("location") or {}
        out.append({
            "id": f"sr:{c['slug']}:{j['id']}", "source": "smartrecruiters", "company": c["name"],
            "title": j["name"], "location": ", ".join(filter(None, [loc.get("city"), "Malaysia"])),
            "url": d.get("postingUrl") or f"https://jobs.smartrecruiters.com/{c['slug']}/{j['id']}",
            "posted": (j.get("releasedDate") or "")[:10],
            "description": strip_html(" ".join(s.get("text", "") for s in sections.values() if isinstance(s, dict))),
        })
    return out


COLLECTORS = {"workday": workday, "greenhouse": greenhouse, "lever": lever, "smartrecruiters": smartrecruiters}


def inbox(folder):
    """Jobs pasted by hand (e.g. from JobStreet or LinkedIn) as .txt files.
    Optional header lines: Title:, Company:, Location:, URL:. Everything else is the ad text."""
    jobs = []
    for f in sorted(Path(folder).glob("*.txt")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        meta = dict(re.findall(r"^(title|company|location|url):\s*(.+)$", text, flags=re.I | re.M))
        meta = {k.lower(): v.strip() for k, v in meta.items()}
        jobs.append({
            "id": f"inbox:{f.stem}", "source": "pasted", "company": meta.get("company", "?"),
            "title": meta.get("title", f.stem.replace("-", " ")), "location": meta.get("location", ""),
            "url": meta.get("url", ""), "posted": "", "description": text,
        })
    return jobs
