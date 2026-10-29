# Job Radar

A small pipeline, run every 4 hours, that finds data analyst, business analyst and data engineering jobs in Malaysia, scores each one against my skills, and publishes a ranked shortlist.

**Live shortlist:** https://muhd-muaz.github.io/job-radar/

## What it does

1. **Collects** postings from public career feeds (Workday, Greenhouse, Lever, SmartRecruiters) for a list of target companies, keeping only Malaysia-based roles with relevant titles.
2. **Adds** jobs from sites that don't allow scraping (JobStreet, LinkedIn, Hiredly, Maukerja) two ways: their own job-alert emails, read from a dedicated mailbox, and ads I paste into [`inbox/dump.txt`](inbox/dump.txt). Optional aggregator APIs (Careerjet, Jooble) switch on when a key is set.
3. **Scores** each job 0-100: title fit, how many of the requested skills I have, a bonus for Kuala Lumpur / Selangor, and a penalty for senior roles or 5+ years of experience.
4. **Finds skill gaps**: counts which skills employers ask for that I don't list yet, so I know what to learn next.
5. **Suggests projects** to mention in each application, based on the skills the ad asks for.
6. **Publishes** a static page (filters, save / applied tracking, skills-to-learn chart, source status) to GitHub Pages and keeps history in SQLite, every morning via GitHub Actions.

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
| `config/discovered.json` | companies found monthly from the [ats-scrapers](https://github.com/kalil0321/ats-scrapers) lists (MIT) that post jobs in Malaysia |
| `config/skills.json` | the skill list (and spellings) used for matching and the gap report |

## Optional secrets (Settings > Secrets and variables > Actions)

| Secret | Turns on |
|---|---|
| `ALERT_IMAP_USER`, `ALERT_IMAP_PASSWORD` | reading job-alert emails (use a mailbox made only for alerts, with an app password) |
| `CAREERJET_AFFID` | Careerjet search API |
| `JOOBLE_KEY` | Jooble search API |
| `NOTIFY_TO` | email of new strong KL/Selangor matches, each job sent once (sent from the alerts mailbox) |

## Data and ethics

Only public, unauthenticated career-site APIs are used, at most once a day, with an identifying user agent. No scraping of LinkedIn, JobStreet or other boards, and no logged-in sessions; those jobs only arrive through the alert emails the sites send. Job descriptions are stored for scoring; the published page shows only title, company, location, link and skills.

The SQLite database is kept on the `data` branch as a single commit, so the main branch's history doesn't grow every day.

## Use it for your own job search (any profession)

Job Radar isn't tied to data jobs. What it collects and how it scores comes from two files:

1. **Copy the repo** (Fork, or "Use this template" on GitHub) and turn on Actions and Pages (Settings → Pages → `main` / `docs`).
2. **`config/profile.json`**: put your own job titles in `target_titles` (for example `"hr executive": 3`, `"admin": 2`, `"mechanical engineer": 3`), your skills in `have_skills`, the skills you're learning in `learning_skills`, and your preferred towns in `preferred_locations`.
3. **`config/companies.json`**: change `workday_search_terms` to your job titles. The monthly discovery run finds companies with jobs in Malaysia by itself.
4. **Your CV stays private.** The public page only carries a sample CV (`config/cv.sample.json`). Press **My resume → Template**, fill in your own details, then **Load my CV**. The file is kept in your browser and never uploaded. Don't commit a real `config/cv.json` (it's in `.gitignore`).
5. **Your CV on any device, without a password.** After loading your CV, press **Make my private link**. It downloads `cv.locked.json` (your CV, encrypted) and copies a link with the key in it. Commit the file to `config/cv.locked.json`, then open the link once in any browser. Only someone with the link can read the CV; keep it like a password.

Alert emails (JobStreet, LinkedIn and others) need a separate Gmail mailbox and two repository secrets. See `inbox/README.md`.
