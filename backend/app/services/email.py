"""Outgoing email. SMTP is optional.

* SMTP_HOST set   -> the message is sent over SMTP.
* not set, dev    -> the message (including any link) is logged to the server console.
* not set, prod   -> an error is logged; nothing is sent (configure SMTP for production).
* APP_ENV=test    -> messages are kept in ``OUTBOX`` for assertions.
"""

import logging
import smtplib
from collections import deque
from email.message import EmailMessage

from app.config import settings

log = logging.getLogger("skillalign.email")
OUTBOX: deque[dict] = deque(maxlen=50)


def send_email(to: str, subject: str, body: str) -> None:
    if settings.is_test:
        OUTBOX.append({"to": to, "subject": subject, "body": body})
        return
    if not settings.smtp_host:
        if settings.app_env == "production":
            log.error("SMTP is not configured; email to %s (%s) was not sent.", to, subject)
        else:
            log.warning("SMTP not configured. Development email:\nTo: %s\nSubject: %s\n\n%s", to, subject, body)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.smtp_from, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException):
        # Never leak SMTP failures to the client (e.g. account enumeration on forgot-password).
        log.exception("Failed to send email to %s (%s)", to, subject)
