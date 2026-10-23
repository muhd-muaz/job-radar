import json
from pathlib import Path

from jobradar import sources
from jobradar.score import build_skill_finder, score

ROOT = Path(__file__).resolve().parent.parent
PROFILE = json.loads((ROOT / "config/profile.json").read_text())
FIND = build_skill_finder(json.loads((ROOT / "config/skills.json").read_text())["skills"])


def job(title, desc):
    return {"title": title, "description": desc}


def test_good_match_beats_senior_role():
    desc = "SQL, Python, Power BI dashboards, ETL pipelines, ERP."
    junior = score(job("Data Analyst", desc), PROFILE, FIND(desc))
    senior = score(job("Senior Manager, Data Analytics", desc + " 10+ years"), PROFILE, FIND(desc))
    assert junior["score"] > senior["score"]
    assert junior["score"] >= 60


def test_gaps_and_projects():
    desc = "Python, SQL, Snowflake and Airflow required."
    s = score(job("Data Engineer", desc), PROFILE, FIND(desc))
    assert {"python", "sql"} <= set(s["matched"])
    assert {"snowflake", "airflow"} <= set(s["missing"])
    assert "Lift breakdown analytics" in s["projects"]


def test_word_boundaries():
    assert "r" not in FIND("R&D department")
    assert "machine learning" in FIND("ML models")
    assert "erp" not in FIND("enterprise")


def test_inbox_parsing():
    jobs = sources.inbox(ROOT / "inbox")
    ex = next(j for j in jobs if j["id"] == "inbox:example-data-analyst")
    assert ex["company"] == "Example Sdn Bhd"
    assert sources.in_malaysia(ex["location"])
