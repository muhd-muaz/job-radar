"""Writes docs/index.html (the shortlist page) and docs/jobs.json."""
import html
import json
from collections import Counter

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Radar</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c1e21;--mute:#667085;--line:#e4e7ec;--acc:#2563eb;--good:#16a34a;--warn:#d97706;--bad:#dc2626}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#181b21;--ink:#e6e8eb;--mute:#98a2b3;--line:#2a2f37;--acc:#60a5fa}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px}h1{margin:0 0 4px;font-size:26px}h2{font-size:17px;margin:28px 0 10px}
.sub{color:var(--mute);margin:0 0 20px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}.card b{display:block;font-size:26px}
.card span{color:var(--mute);font-size:13px}.bars{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 16px}
.bar{display:grid;grid-template-columns:150px 1fr 40px;gap:10px;align-items:center;margin:5px 0;font-size:14px}
.bar i{display:block;height:10px;border-radius:5px;background:var(--warn)}.bar i.l{background:var(--acc)}
input{width:100%;padding:10px 14px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);font-size:15px;margin-bottom:10px}
.job{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin-bottom:10px;display:grid;grid-template-columns:56px 1fr;gap:14px}
.sc{font-size:22px;font-weight:700;text-align:center;border-radius:10px;padding:8px 0;background:var(--bg)}
.hi{color:var(--good)}.mid{color:var(--warn)}.lo{color:var(--mute)}
.job a{color:var(--ink);font-weight:600;text-decoration:none}.job a:hover{color:var(--acc)}
.meta{color:var(--mute);font-size:13px}.chips{margin-top:6px;display:flex;flex-wrap:wrap;gap:4px}
.chip{font-size:12px;padding:2px 8px;border-radius:99px;border:1px solid var(--line)}.chip.m{border-color:var(--good);color:var(--good)}
.chip.x{border-color:var(--warn);color:var(--warn)}.chip.p{border-color:var(--acc);color:var(--acc)}.new{color:var(--acc);font-size:12px;font-weight:700}
footer{color:var(--mute);font-size:13px;margin-top:30px}footer a{color:var(--mute)}
@media (max-width:560px){.bar{grid-template-columns:110px 1fr 30px}}
</style></head><body><main>
<h1>Job Radar</h1>
<p class="sub">Data analyst, BA and data engineering roles in Malaysia, collected from public career feeds and scored against my skills. Updated __TODAY__.</p>
<div class="cards">
<div class="card"><b>__N__</b><span>open matches</span></div>
<div class="card"><b>__NEW__</b><span>new today</span></div>
<div class="card"><b>__STRONG__</b><span>score 60+</span></div>
<div class="card"><b>__FEEDS__</b><span>feeds working today</span></div>
</div>
<h2>Skills employers ask for that I don't list yet</h2>
<div class="bars">__BARS__</div>
<p class="meta">Blue = already learning. Count = open matches that mention the skill.</p>
<h2>Shortlist</h2>
<input id="q" placeholder="Filter by title, company or skill">
<div id="list">__JOBS__</div>
<footer>Built with Python + SQLite, runs daily on GitHub Actions. Sources: public Workday, Greenhouse, Lever and SmartRecruiters feeds, plus ads pasted by hand. Source code: <a href="https://github.com/muhd-muaz/job-radar">github.com/muhd-muaz/job-radar</a></footer>
</main><script>
const q=document.getElementById('q'),jobs=[...document.querySelectorAll('.job')];
q.addEventListener('input',()=>{const t=q.value.toLowerCase();jobs.forEach(j=>j.style.display=j.textContent.toLowerCase().includes(t)?'':'none')});
</script></body></html>"""


def _e(s):
    return html.escape(str(s or ""))


def build(outdir, active, runs, profile, today):
    outdir.mkdir(exist_ok=True)
    gaps = Counter(s for j in active for s in j["missing"])
    learning = set(profile.get("learning_skills", []))
    top = gaps.most_common(12)
    peak = max([n for _, n in top] or [1])
    bars = "".join(f'<div class="bar"><span>{_e(s)}</span><i class="{"l" if s in learning else ""}" '
                   f'style="width:{n / peak * 100:.0f}%"></i><span>{n}</span></div>' for s, n in top) or "<p>No data yet.</p>"
    cards = []
    for j in active:
        cls = "hi" if j["score"] >= 60 else "mid" if j["score"] >= 40 else "lo"
        chips = "".join(f'<span class="chip m">{_e(s)}</span>' for s in j["matched"])
        chips += "".join(f'<span class="chip x">{_e(s)}</span>' for s in j["missing"])
        chips += "".join(f'<span class="chip p">show: {_e(p)}</span>' for p in j["projects"][:2])
        new = ' <span class="new">NEW</span>' if j["first_seen"] == today else ""
        link = f'<a href="{_e(j["url"])}" target="_blank" rel="noopener">{_e(j["title"])}</a>' if j["url"] else f"<b>{_e(j['title'])}</b>"
        cards.append(f'<div class="job"><div class="sc {cls}">{j["score"]}</div><div>{link}{new}'
                     f'<div class="meta">{_e(j["company"])} · {_e(j["location"])} · {_e(j["source"])} · seen since {_e(j["first_seen"])}</div>'
                     f'<div class="chips">{chips}</div></div></div>')
    page = (PAGE.replace("__TODAY__", today).replace("__N__", str(len(active)))
            .replace("__NEW__", str(sum(j["first_seen"] == today for j in active)))
            .replace("__STRONG__", str(sum(j["score"] >= 60 for j in active)))
            .replace("__FEEDS__", f'{sum(r["ok"] for r in runs)}/{len(runs)}' if runs else "-")
            .replace("__BARS__", bars).replace("__JOBS__", "".join(cards) or "<p>No matches yet.</p>"))
    (outdir / "index.html").write_text(page, encoding="utf-8")
    slim = [{k: j[k] for k in ("company", "title", "location", "url", "score", "first_seen", "matched", "missing")} for j in active]
    (outdir / "jobs.json").write_text(json.dumps(slim, indent=1), encoding="utf-8")
