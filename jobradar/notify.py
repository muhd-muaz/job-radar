"""Email of new strong matches, sent from the alerts mailbox.
Needs ALERT_IMAP_USER / ALERT_IMAP_PASSWORD (same Gmail app password) and NOTIFY_TO. Silent when nothing is new."""
import html
import os
import smtplib
from email.message import EmailMessage

PAGE = "https://muhd-muaz.github.io/job-radar/"


def pick(active, today, profile, min_score=60):
    local = profile.get("preferred_locations", [])
    new = [j for j in active if j["first_seen"] == today and j["score"] >= min_score
           and any(w in (j["location"] + " ").lower() for w in local)]
    return sorted(new, key=lambda j: -j["score"])[:15]


def send_new_matches(db, active, today, profile):
    user, pw, to = (os.environ.get(k) for k in ("ALERT_IMAP_USER", "ALERT_IMAP_PASSWORD", "NOTIFY_TO"))
    if not (user and pw and to):
        return
    sent = {r[0] for r in db.execute("SELECT id FROM notified")}  # runs every 4 hours; each job is emailed once
    new = [j for j in pick(active, today, profile) if j["id"] not in sent]
    if not new:
        print("notify: no new strong matches, no email")
        return
    msg = EmailMessage()
    msg["Subject"] = f"Job radar: {len(new)} new strong match{'es' if len(new) > 1 else ''} in KL/Selangor"
    msg["From"], msg["To"] = user, to
    lines = [f"{j['score']}  {j['title']} - {j['company']} ({j['location']})\n    {j['url']}" for j in new]
    msg.set_content("\n".join(lines) + f"\n\nFull list: {PAGE}")
    rows = "".join(
        f'<tr><td style="padding:6px 10px;font-weight:700">{j["score"]}</td><td style="padding:6px 10px">'
        f'<a href="{html.escape(j["url"])}">{html.escape(j["title"])}</a><br>'
        f'<span style="color:#667085">{html.escape(j["company"])} · {html.escape(j["location"])}</span></td></tr>'
        for j in new)
    msg.add_alternative(f'<table style="font:14px system-ui,sans-serif">{rows}</table>'
                        f'<p><a href="{PAGE}">Open the full shortlist</a></p>', subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(user, pw.replace(" ", ""))
        s.send_message(msg)
    db.executemany("INSERT OR IGNORE INTO notified VALUES (?,?)", [(j["id"], today) for j in new])
    db.commit()
    print(f"notify: emailed {len(new)} new matches")
