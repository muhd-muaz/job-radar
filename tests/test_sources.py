from jobradar import sources

TARGETS = ["data analyst", "data engineer"]


def test_workday_keeps_only_malaysia(monkeypatch):
    def fake(url, payload=None, timeout=30):
        if url.endswith("/jobs"):
            if payload["offset"]:
                return {"jobPostings": []}
            return {"jobPostings": [
                {"title": "Data Analyst", "externalPath": "/job/KL/Data-Analyst_R1", "locationsText": "Kuala Lumpur, Malaysia"},
                {"title": "Data Engineer", "externalPath": "/job/SG/DE_R2", "locationsText": "Singapore"},
                {"title": "Data Engineer", "externalPath": "/job/X/DE_R3", "locationsText": "2 Locations"},
                {"title": "Chef", "externalPath": "/job/KL/Chef_R4", "locationsText": "Kuala Lumpur"},
            ]}
        rid = url.rsplit("_", 1)[1]
        loc = {"R1": "Kuala Lumpur, Malaysia", "R3": "Bangalore, India"}[rid]
        return {"jobPostingInfo": {"title": "x", "jobReqId": rid, "location": loc,
                                   "jobDescription": "<p>SQL</p>", "startDate": "2026-10-20"}}
    monkeypatch.setattr(sources, "http_json", fake)
    c = {"name": "Acme", "host": "acme.wd1.myworkdayjobs.com", "tenant": "acme", "site": "Ext"}
    jobs = sources.workday(c, TARGETS, ["data"])
    assert [j["id"] for j in jobs] == ["wd:acme:R1"]
    assert jobs[0]["description"] == "SQL"


def test_greenhouse(monkeypatch):
    monkeypatch.setattr(sources, "http_json", lambda url, **k: {"jobs": [
        {"id": 1, "title": "Data Analyst", "location": {"name": "Kuala Lumpur"}, "content": "&lt;p&gt;Python&lt;/p&gt;"},
        {"id": 2, "title": "Data Analyst", "location": {"name": "Jakarta"}, "content": ""},
    ]})
    jobs = sources.greenhouse({"name": "G", "slug": "g"}, TARGETS, [])
    assert len(jobs) == 1 and jobs[0]["description"] == "Python"
