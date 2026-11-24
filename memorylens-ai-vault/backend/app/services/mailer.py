"""
Minimal SMTP mailer for OTP/verification emails.

Uses stdlib smtplib + EmailMessage only (no third-party mail SDK — this is a
capstone project, not a production mail pipeline). If SMTP isn't configured
via env vars, or the real send fails for any reason, we degrade to a
dev-mode console log instead of raising, so callers (auth flows) never break
because mail delivery is unavailable.
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def _dev_log(to: str, subject: str, body: str) -> None:
    print(
        "[DEV MODE — email not sent, SMTP not configured]\n"
        f"To: {to}\n"
        f"Subject: {subject}\n"
        f"Body:\n{body}\n"
    )


def send_email(to: str, subject: str, body: str) -> None:
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")

    if not host or not user:
        _dev_log(to, subject, body)
        return

    port = int(os.environ.get("SMTP_PORT", "587"))
    password = os.environ.get("SMTP_PASSWORD", "")
    sender = os.environ.get("SMTP_FROM", user)
    use_tls = os.environ.get("SMTP_USE_TLS", "true").strip().lower() not in ("0", "false", "no")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            if use_tls:
                smtp.starttls()
            if password:
                smtp.login(user, password)
            smtp.send_message(msg)
    except Exception:
        logger.exception("SMTP send failed; falling back to dev-mode log")
        _dev_log(to, subject, body)
