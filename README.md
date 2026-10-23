# Job Radar

A small daily pipeline that finds data analyst, business analyst and data engineering jobs in Malaysia, scores each one against my skills, and publishes a ranked shortlist.

**Live shortlist:** https://muhd-muaz.github.io/job-radar/

## What it does

1. **Collects** postings from public career feeds (Workday, Greenhouse, Lever, SmartRecruiters) for a list of target companies, keeping only Malaysia-based roles with relevant titles.
2. **Adds** job ads I paste by hand into [`inbox/`](inbox/) (for sites like JobStreet and LinkedIn, which don't allow scraping).
3. **Scores** each job 0-100: title fit, how many of the requested skills I have, and a penalty for senior roles or 5+ years of experience.
4. **Finds skill gaps**: counts which skills employers ask for that I don't list yet, so I know what to learn next.
5. **Suggests projects** to mention in each application, based on the skills the ad asks for.
6. **Publishes** a static page to GitHub Pages and keeps history in SQLite, every morning via GitHub Actions.

```
career feeds ─┐
              ├─> collect ─> score + skill gaps ─> SQLite ─> docs/index.html (GitHub Pages)
inbox/*.txt ──┘
```

## Run it yourself

Python 3.10+, no extra packages needed.

```
python -m jobradar            # collect, score, rebuild docs/
python -m jobradar check      # test each company feed
python -m jobradar --offline  # only score pasted ads in inbox/
python -m pytest tests        # tests (needs pytest)
```

## Configure

| File | What it controls |
|---|---|
| `config/profile.json` | target titles, my skills and weights, skills I'm learning, my projects, seniority penalties |
| `config/companies.json` | which companies to collect from and how |
| `config/skills.json` | the skill list (and spellings) used for matching and the gap report |

## Data and ethics

Only public, unauthenticated career-site APIs are used, at most once a day, with an identifying user agent. No LinkedIn or JobStreet scraping. Job descriptions are stored for scoring; the published page shows only title, company, location, link and skills.
