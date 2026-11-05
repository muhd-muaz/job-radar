"""Collectors for public career feeds. Each returns a list of job dicts:
{id, source, company, title, location, url, posted, description}
"""
import email
import hashlib
import html
import imaplib
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from .score import any_has

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


ALL = []  # every Malaysian job seen this run, any field: published as docs/all.json for the page's "search everything"


def seen_any(c, title, location, url, posted=""):
    if title and in_malaysia(location):
        ALL.append([title.strip(), c["name"], location, url, (posted or "")[:10]])


def title_wanted(title, targets):
    t = (title or "").lower()
    return any_has(targets, t)


def workday(c, targets, terms):
    base = f"https://{c['host']}/wday/cxs/{c['tenant']}/{c['site']}"
    seen, jobs = set(), []
    for term in c.get("terms", terms):
        for offset in range(0, 100, 20):
            res = http_json(f"{base}/jobs", {"appliedFacets": {}, "limit": 20, "offset": offset,
                                             "searchText": f"{term} Malaysia"})
            posts = res.get("jobPostings", [])
            for p in posts:
                path = p.get("externalPath", "")
                if path in seen:
                    continue
                if not title_wanted(p.get("title"), targets):
                    seen.add(path)
                    loc = p.get("locationsText", "")  # "2 Locations" from a Malaysia search is kept, without a detail fetch
                    seen_any(c, p.get("title"), "Malaysia (several locations)" if "locations" in loc.lower() else loc,
                             f"https://{c['host']}/{c['site']}{path}")
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
    # the board list without descriptions is small; the full text is fetched only for wanted jobs in Malaysia
    base = f"https://boards-api.greenhouse.io/v1/boards/{c['slug']}/jobs"
    out = []
    for j in http_json(base).get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        if not title_wanted(j["title"], targets):
            seen_any(c, j["title"], loc, j.get("absolute_url", ""), j.get("updated_at"))
        elif in_malaysia(loc):
            full = http_json(f"{base}/{j['id']}")
            out.append({
                "id": f"gh:{c['slug']}:{j['id']}", "source": "greenhouse", "company": c["name"],
                "title": j["title"], "location": loc, "url": j.get("absolute_url", ""),
                "posted": (j.get("updated_at") or "")[:10],
                "description": strip_html(html.unescape(full.get("content", ""))),
            })
    return out


def lever(c, targets, terms):
    res = http_json(f"https://api.lever.co/v0/postings/{c['slug']}?mode=json")
    out = []
    for j in res:
        loc = ", ".join((j.get("categories") or {}).get("allLocations") or [(j.get("categories") or {}).get("location", "")])
        if not title_wanted(j.get("text"), targets):
            seen_any(c, j.get("text"), loc, j.get("hostedUrl", ""))
        elif in_malaysia(loc):
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
            loc = j.get("location") or {}
            seen_any(c, j.get("name"), ", ".join(filter(None, [loc.get("city"), "Malaysia"])),
                     f"https://jobs.smartrecruiters.com/{c['slug']}/{j['id']}", j.get("releasedDate"))
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


class Skip(Exception):
    """Feed switched off on purpose (e.g. no API key set)."""


def careerjet(c, targets, terms):
    """Careerjet public search API (aggregates Malaysian job boards). Needs a free affiliate id."""
    affid = os.environ.get("CAREERJET_AFFID")
    if not affid:
        raise Skip("CAREERJET_AFFID not set")
    out = []
    for term in terms:
        for loc in c.get("locations", ["Kuala Lumpur", "Selangor"]):
            q = urllib.parse.urlencode({"locale_code": "en_MY", "keywords": term, "location": loc, "affid": affid,
                                        "pagesize": 99, "sort": "date", "user_ip": "127.0.0.1", "user_agent": UA})
            for j in http_json(f"http://public.api.careerjet.net/search?{q}").get("jobs", []):
                if title_wanted(j.get("title"), targets):
                    out.append({
                        "id": f"cj:{j.get('url')}", "source": "careerjet", "company": j.get("company") or "?",
                        "title": j["title"], "location": j.get("locations") or loc, "url": j.get("url", ""),
                        "posted": j.get("date", ""), "description": strip_html(j.get("description")),
                    })
    return out


def jooble(c, targets, terms):
    """Jooble REST API (aggregator). Needs a free API key."""
    key = os.environ.get("JOOBLE_KEY")
    if not key:
        raise Skip("JOOBLE_KEY not set")
    out = []
    for term in terms:
        for loc in c.get("locations", ["Kuala Lumpur", "Selangor"]):
            res = http_json(f"https://jooble.org/api/{key}", {"keywords": term, "location": f"{loc}, Malaysia"})
            for j in res.get("jobs", []):
                if title_wanted(j.get("title"), targets):
                    out.append({
                        "id": f"jb:{j.get('id')}", "source": f"jooble ({j.get('source', '')})".replace(" ()", ""),
                        "company": j.get("company") or "?", "title": strip_html(j["title"]),
                        "location": j.get("location") or loc, "url": j.get("link", ""),
                        "posted": (j.get("updated") or "")[:10], "description": strip_html(j.get("snippet")),
                    })
    return out


NOTES = {}  # per-collector diagnostics for the runs table
ALERT_SENDERS = ("jobstreet", "linkedin", "hiredly", "maukerja", "indeed", "glints", "jobsdb", "ricebowl")


def email_alerts(c, targets, terms):
    """Job-alert emails that JobStreet, LinkedIn, Hiredly, Maukerja etc. send to a mailbox.
    Reads the last few days over IMAP. Use a separate mailbox made only for job alerts."""
    user, pw = os.environ.get("ALERT_IMAP_USER"), os.environ.get("ALERT_IMAP_PASSWORD")
    if not (user and pw):
        raise Skip("ALERT_IMAP_USER / ALERT_IMAP_PASSWORD not set")
    box = imaplib.IMAP4_SSL(c.get("imap_host", "imap.gmail.com"))
    box.login(user, pw.replace(" ", ""))
    box.select("INBOX", readonly=True)
    since = (date.today() - timedelta(days=c.get("days", 4))).strftime("%d-%b-%Y")
    _, ids = box.search(None, "SINCE", since)
    out, seen, wanted = [], {}, []
    all_ids = ids[0].split()
    # one round trip for every sender, then one for the bodies of alert mails only
    if all_ids:
        _, heads = box.fetch(b",".join(all_ids), "(BODY.PEEK[HEADER.FIELDS (FROM)])")
        for part in heads:
            if not isinstance(part, tuple):
                continue
            mid = part[0].split()[0]
            sender = (email.message_from_bytes(part[1]).get("From") or "").lower()
            site = next((s for s in ALERT_SENDERS if s in sender), None)
            if site:
                wanted.append((mid, site))
            else:
                dom = sender.rsplit("@", 1)[-1].strip("> ") if "@" in sender else "?"
                seen[dom] = seen.get(dom, 0) + 1
    if wanted:
        site_of = dict(wanted)
        _, data = box.fetch(b",".join(m for m, _ in wanted), "(BODY.PEEK[])")
        for part in data:
            if not isinstance(part, tuple):
                continue
            site = site_of[part[0].split()[0]]
            msg = email.message_from_bytes(part[1])
            body = next((p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", "ignore")
                         for p in msg.walk() if p.get_content_type() == "text/html"), "")
            got = parse_alert_html(body, site, targets)
            seen[site] = seen.get(site, 0) + 1
            seen[site + " jobs"] = seen.get(site + " jobs", 0) + len(got)
            out += got
    box.logout()
    # kept in the runs table so a 0 can be told apart: no mail arriving, or mail the parser can't read
    NOTES["email_alerts"] = f"{len(all_ids)} emails since {since}; by sender: {seen}"
    return out


_STATES = r"Kuala Lumpur|Selangor|Penang|Pulau Pinang|Johor|Putrajaya|Cyberjaya|Perak|Kedah|Melaka|Malacca|Sabah|Sarawak|" \
          r"Negeri Sembilan|Pahang|Terengganu|Kelantan|Perlis|Labuan|Malaysia"
_COMPANY_END = re.compile(r"^(.*?\b(?:Sdn\.? ?Bhd\.?|Berhad|Bhd\.?|Limited|Ltd\.?|Inc\.?|PLC|LLP))\s+(.+)$", re.I)


def alert_who_where(lines):
    """Company, location and pay from the text under an alert's job link.
    LinkedIn writes "Company · Place"; JobStreet runs "Company Suburb, State RM3,000 – RM4,000 per month" together."""
    text = " ".join(lines)
    pay = re.search(r"RM\s?[\d,]+(?:\s*[–-]\s*RM\s?[\d,]+)?(?:\s*per month)?", text)
    text = re.sub(r"RM\s?[\d,]+.*$", "", text)                            # pay and anything after it
    text = re.sub(r"\b(Posted on|Application started) \d{1,2} \w+ \d{4}", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" ·")
    if " · " in text:
        company, place = text.split(" · ", 1)
        return company.strip(), place.strip(), pay and pay.group(0)
    m = _COMPANY_END.match(text)
    if m and re.search(_STATES, m.group(2)):
        return m.group(1).strip(), m.group(2).strip(), pay and pay.group(0)
    # no company ending to cut at: take "Suburb, State" (up to two words before the comma) or a bare state at the end
    m = re.search(r"((?:\S+ )?\S+, (?:%s)|(?:%s))$" % (_STATES, _STATES), text)
    if m and m.start() > 0:
        return text[:m.start()].strip(), m.group(1), pay and pay.group(0)
    return text, "", pay and pay.group(0)


def parse_alert_html(body, site, targets):
    """Pull job links out of an alert email: any link whose text looks like a wanted job title."""
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', body, flags=re.S | re.I):
        href, title = m.group(1), strip_html(m.group(2))
        if not (5 < len(title) < 120) or not title_wanted(title, targets):
            continue
        # the lines right after the link usually hold company and location
        nxt = body[m.end():m.end() + 1500].split("<a ", 1)[0]
        nxt = re.sub(r"<[^>]*$", "", nxt)   # the 1,500-character cut can end inside a tag
        rest = [l.strip() for l in strip_html(nxt).split("\n") if l.strip()][:2]
        company, place, pay = alert_who_where(rest)
        key = (title, rest[0] if rest else "")   # same title at different companies = different jobs
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "id": f"mail:{site}:{title}:{rest[0] if rest else ''}".lower(), "source": f"{site} alert",
            "company": company or "?", "title": title, "location": place,
            "url": html.unescape(href), "posted": "", "description": " ".join(rest),
        })
    return out


COLLECTORS = {"workday": workday, "greenhouse": greenhouse, "lever": lever, "smartrecruiters": smartrecruiters,
              "careerjet": careerjet, "jooble": jooble, "email_alerts": email_alerts}


DUMP_HEADER = """PASTE JOB ADS BELOW THE LINE. Old or new, as many as you like.
Put a line with --- between ads (or start each ad with its link). Each run reads everything and files
new ads away; ads it already has are skipped, so clear this file whenever you like.
Easier: use "Add a job ad from anywhere" on the website instead (private to your browser).
==================== PASTE BELOW ====================
"""
SEPARATOR = re.compile(r"^\s*(-{3,}|={3,}|\*{3,}|_{3,})\s*$")
AD_LINK = re.compile(r"^\s*https?://\S*(jobstreet|linkedin\.com/jobs|hiredly|maukerja|indeed|glints)\S*\s*$", re.I)


def split_dump(text):
    """Split a free-form paste into separate ads."""
    if "PASTE BELOW" in text:
        text = text.split("PASTE BELOW", 1)[1].split("\n", 1)[-1]
    ads, cur = [], []
    for line in text.splitlines():
        if SEPARATOR.match(line) or (AD_LINK.match(line) and len("\n".join(cur).strip()) > 40):
            ads.append("\n".join(cur))
            cur = [] if SEPARATOR.match(line) else [line]
        else:
            cur.append(line)
    ads.append("\n".join(cur))
    return [a.strip() for a in ads if len(a.strip()) > 40]


def parse_ad(text):
    """Guess title, company, location and link from a pasted ad. Header lines (Title: ...) win."""
    meta = {k.lower(): v.strip() for k, v in re.findall(r"^(title|company|location|url):\s*(.+)$", text, flags=re.I | re.M)}
    url = meta.get("url") or next(iter(re.findall(r"https?://\S+", text)), "")
    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("http")
             and not re.match(r"^(title|company|location|url):", l.strip(), re.I)]
    short = [l for l in lines if len(l) < 100]
    loc = meta.get("location") or next((l for l in short[:12] if in_malaysia(l)), "")
    title = meta.get("title") or (short[0] if short else "Pasted job")
    company = meta.get("company") or next((l for l in short[1:4] if l != loc), "?")
    key = re.sub(r"\W+", " ", text.lower())[:400]
    return {
        "id": "paste:" + hashlib.sha1(key.encode()).hexdigest()[:12], "source": "pasted",
        "company": company, "title": title, "location": loc, "url": url, "posted": "", "description": text,
    }


def inbox(folder, archive, keep_days=30, today=None):
    """Jobs pasted by hand (JobStreet, LinkedIn, Hiredly, Maukerja...). New ads from inbox/dump.txt and any
    inbox/*.txt are added to the archive (data/pasted.jsonl), then dump.txt is emptied.
    Returns archived ads added in the last keep_days days."""
    today = today or date.today().isoformat()
    folder, archive = Path(folder), Path(archive)
    old = {}
    if archive.exists():
        for line in archive.read_text(encoding="utf-8").splitlines():
            if line.strip():
                j = json.loads(line)
                old[j["id"]] = j
    dump = folder / "dump.txt"
    texts = split_dump(dump.read_text(encoding="utf-8", errors="ignore")) if dump.exists() else []
    for f in sorted(folder.glob("*.txt")):
        if f.name != "dump.txt" and not f.name.startswith("example"):
            texts.append(f.read_text(encoding="utf-8", errors="ignore"))
    added = 0
    for t in texts:
        j = parse_ad(t)
        if j["id"] not in old:
            old[j["id"]] = {**j, "added": today}
            added += 1
    archive.parent.mkdir(exist_ok=True)
    archive.write_text("".join(json.dumps(j, ensure_ascii=False) + "\n" for j in old.values()), encoding="utf-8")
    # The scheduled run never writes to inbox/: you own that folder, the bot owns docs/ and data/,
    # so a run can't overwrite ads you paste while it is going. Local runs still tidy the file.
    if not os.environ.get("GITHUB_ACTIONS"):
        dump.write_text(DUMP_HEADER, encoding="utf-8")
    cutoff = (date.fromisoformat(today) - timedelta(days=keep_days)).isoformat()
    print(f"inbox: {len(texts)} ads read, {added} new, {len(old)} in archive")
    return [{k: v for k, v in j.items() if k != "added"} for j in old.values() if j["added"] >= cutoff]
