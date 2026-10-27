"""Find companies that currently post jobs in Malaysia.

Reads the open company lists from github.com/kalil0321/ats-scrapers (MIT), checks each company's public
job board once, and writes the ones with Malaysian postings to config/discovered.json.
Run monthly:  python -m jobradar.discover
"""
import csv
import io
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .sources import UA, http_json, in_malaysia

LISTS = "https://raw.githubusercontent.com/kalil0321/ats-scrapers/main/ats-companies/{}.csv"
ROOT = Path(__file__).resolve().parent.parent


def load_list(ats):
    req = urllib.request.Request(LISTS.format(ats), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode("utf-8"))))


def to_entry(ats, row):
    """Company list row -> companies.json entry."""
    if ats == "workday":
        host = row["url"].split("/")[2]
        tenant, site = row["slug"].split("/", 1)
        return {"name": row["name"], "ats": ats, "host": host, "tenant": tenant, "site": site}
    return {"name": row["name"], "ats": ats, "slug": row["slug"]}


def has_malaysia_jobs(e):
    """True when the board shows at least one Malaysia posting. One request per company."""
    ats = e["ats"]
    if ats == "workday":
        res = http_json(f"https://{e['host']}/wday/cxs/{e['tenant']}/{e['site']}/jobs",
                        {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "Malaysia"}, timeout=20)
        return any(in_malaysia(p.get("locationsText")) for p in res.get("jobPostings", []))
    if ats == "greenhouse":
        res = http_json(f"https://boards-api.greenhouse.io/v1/boards/{e['slug']}/jobs", timeout=20)
        return any(in_malaysia((j.get("location") or {}).get("name")) for j in res.get("jobs", []))
    if ats == "lever":
        res = http_json(f"https://api.lever.co/v0/postings/{e['slug']}?mode=json", timeout=20)
        return any(in_malaysia(" ".join((j.get("categories") or {}).get("allLocations") or [])) for j in res)
    if ats == "smartrecruiters":
        res = http_json(f"https://api.smartrecruiters.com/v1/companies/{e['slug']}/postings?country=my&limit=1", timeout=20)
        return res.get("totalFound", 0) > 0
    return False


def check(e):
    try:
        return e if has_malaysia_jobs(e) else None
    except Exception:
        return None


def main(argv):
    known = json.loads((ROOT / "config" / "companies.json").read_text(encoding="utf-8"))["companies"]
    seen = {(c.get("host") or c.get("slug") or "").lower() for c in known}
    todo = []
    for ats in ("workday", "greenhouse", "lever", "smartrecruiters"):
        for row in load_list(ats):
            try:
                e = to_entry(ats, row)
            except (KeyError, ValueError, IndexError):
                continue
            if (e.get("host") or e.get("slug") or "").lower() not in seen:
                todo.append(e)
    limit = int(argv[0]) if argv else len(todo)
    print(f"checking {min(limit, len(todo))} companies")
    with ThreadPoolExecutor(16) as pool:
        found = [e for e in pool.map(check, todo[:limit]) if e]
    found.sort(key=lambda e: e["name"].lower())
    out = ROOT / "config" / "discovered.json"
    out.write_text(json.dumps({"_note": "Written by `python -m jobradar.discover` (monthly). Companies from "
                               "github.com/kalil0321/ats-scrapers with Malaysian postings.",
                               "companies": found}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(found)} companies with Malaysian jobs -> {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
