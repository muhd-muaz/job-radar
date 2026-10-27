import json
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, source TEXT, company TEXT, title TEXT, location TEXT, url TEXT,
  posted TEXT, description TEXT, first_seen TEXT, last_seen TEXT,
  score INTEGER, matched TEXT, missing TEXT, learning TEXT, projects TEXT
);
CREATE TABLE IF NOT EXISTS runs (
  run_date TEXT, source TEXT, company TEXT, ok INTEGER, jobs INTEGER, error TEXT
);
"""


def connect(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def upsert(db, job, s, today):
    db.execute("""
      INSERT INTO jobs VALUES (:id,:source,:company,:title,:location,:url,:posted,:description,
                               :today,:today,:score,:matched,:missing,:learning,:projects)
      ON CONFLICT(id) DO UPDATE SET title=excluded.title, location=excluded.location, url=excluded.url,
        description=excluded.description, last_seen=excluded.last_seen, score=excluded.score,
        matched=excluded.matched, missing=excluded.missing, learning=excluded.learning, projects=excluded.projects
    """, {**job, "today": today, "score": s["score"],
          **{k: json.dumps(s[k]) for k in ("matched", "missing", "learning", "projects")}})


def log_run(db, today, source, company, ok, n, error=""):
    db.execute("INSERT INTO runs VALUES (?,?,?,?,?,?)", (today, source, company, int(ok), n, error[:300]))


def active_jobs(db, since):
    return _rows(db.execute("SELECT * FROM jobs WHERE last_seen >= ? ORDER BY score DESC, first_seen DESC", (since,)))


def closed_jobs(db, since, oldest):
    """Jobs that dropped out of their feed recently (closed or filled)."""
    return _rows(db.execute("SELECT * FROM jobs WHERE last_seen < ? AND last_seen >= ?", (since, oldest)))


def post_counts(db):
    """How many separate postings each (company, title) has had: >1 means reposted."""
    return {(c.lower(), t.strip().lower()): n for c, t, n in db.execute(
        "SELECT company, title, COUNT(*) FROM jobs GROUP BY lower(company), lower(trim(title))")}


def _rows(rows):
    out = []
    for r in rows:
        d = dict(r)
        for k in ("matched", "missing", "learning", "projects"):
            d[k] = json.loads(d[k] or "[]")
        out.append(d)
    return out
