"""Quick check of the alerts mailbox: can we log in, how many job-alert emails are there, can we send."""
import imaplib
import os
import smtplib
from email.message import EmailMessage

from .sources import ALERT_SENDERS

user, pw, to = (os.environ.get(k, "") for k in ("ALERT_IMAP_USER", "ALERT_IMAP_PASSWORD", "NOTIFY_TO"))
print("secrets set:", {"ALERT_IMAP_USER": bool(user), "ALERT_IMAP_PASSWORD": bool(pw), "NOTIFY_TO": bool(to)})
box = imaplib.IMAP4_SSL("imap.gmail.com")
box.login(user, pw.replace(" ", ""))
box.select("INBOX", readonly=True)
_, ids = box.search(None, "ALL")
senders = {}
for mid in ids[0].split()[-200:]:
    _, data = box.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (FROM)])")
    frm = data[0][1].decode(errors="ignore").lower()
    site = next((s for s in ALERT_SENDERS if s in frm), "other")
    senders[site] = senders.get(site, 0) + 1
box.logout()
print("IMAP login OK. Emails in inbox by sender:", senders)
if to:
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = "Job radar: test email", user, to
    msg.set_content("This is a test from job-radar. The daily email of new strong matches will look similar.")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(user, pw.replace(" ", ""))
        s.send_message(msg)
    print("Test email sent to NOTIFY_TO")
