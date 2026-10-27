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


def test_inbox_dump(tmp_path):
    inbox, archive = tmp_path / "inbox", tmp_path / "data" / "pasted.jsonl"
    inbox.mkdir()
    ad1 = (ROOT / "tests/fixtures/ad-with-headers.txt").read_text()
    ad2 = """Business Analyst
Contoso Bhd
Shah Alam, Selangor
We need someone to gather business requirements, run UAT and build Power BI dashboards. SQL is a plus."""
    ad3 = """https://www.jobstreet.com.my/job/999
Data Engineer
Fabrikam Sdn Bhd
Cyberjaya
Build ETL pipelines in Python and Airflow on AWS. 2 years of experience."""
    (inbox / "dump.txt").write_text(sources.DUMP_HEADER + ad1 + "\n---\n" + ad2 + "\n\n" + ad3 + "\n---\n" + ad2)
    jobs = sources.inbox(inbox, archive, today="2026-10-27")
    assert sorted(j["title"] for j in jobs) == ["Business Analyst", "Data Analyst (example)", "Data Engineer"]
    de = next(j for j in jobs if j["title"] == "Data Engineer")
    assert (de["company"], de["location"], de["url"]) == ("Fabrikam Sdn Bhd", "Cyberjaya", "https://www.jobstreet.com.my/job/999")
    ba = next(j for j in jobs if j["title"] == "Business Analyst")
    assert (ba["company"], ba["location"]) == ("Contoso Bhd", "Shah Alam, Selangor")
    # dump is emptied, and pasting the same ad again adds nothing
    assert (inbox / "dump.txt").read_text() == sources.DUMP_HEADER
    (inbox / "dump.txt").write_text(ad2)
    assert len(sources.inbox(inbox, archive, today="2026-10-28")) == 3
    # ads older than 30 days drop off the list but stay archived
    assert sources.inbox(inbox, archive, today="2026-12-15") == []
    assert len(archive.read_text().splitlines()) == 3


def test_full_time_entry_level_beats_contract():
    desc = "SQL, Python, Power BI dashboards. Fresh graduates are welcome."
    perm = score(job("Data Analyst", desc), PROFILE, FIND(desc))
    contract = score(job("Data Analyst (6 months contract)", desc), PROFILE, FIND(desc))
    intern = score(job("Data Analyst Intern", desc), PROFILE, FIND(desc))
    assert perm["score"] >= 80
    assert contract["score"] <= 45 and intern["score"] <= 45


def test_salary_and_notify_pick():
    from jobradar.notify import pick
    from jobradar.report import salary
    assert salary("Salary RM 4,000 - RM 6,000 monthly") == "RM 4,000 – 6,000"
    assert salary("RM 60,000 - 90,000 per annum") == ""
    jobs = [{"first_seen": "2026-10-27", "score": 70, "location": "Kuala Lumpur"},
            {"first_seen": "2026-10-27", "score": 70, "location": "Penang"},
            {"first_seen": "2026-10-26", "score": 90, "location": "Kuala Lumpur"},
            {"first_seen": "2026-10-27", "score": 50, "location": "Selangor"}]
    assert pick(jobs, "2026-10-27", PROFILE) == [jobs[0]]


def test_title_decides_track():
    desc = "SQL, Python, Power BI dashboards, ETL pipelines, data warehouse, KPI reporting."
    de = score(job("Data Engineer", desc), PROFILE, FIND(desc))
    acct = score(job("Financial Reporting Accountant", desc), PROFILE, FIND(desc))
    other = score(job("Enterprise Resiliency Officer", desc), PROFILE, FIND(desc))
    assert de["score"] >= 80 and acct["score"] <= 50 and other["score"] <= 50
