from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

from tenacity import retry, stop_after_attempt, wait_exponential

LOGGER = logging.getLogger(__name__)


class EmailConfigError(RuntimeError):
    pass


REQUIRED_EMAIL_ENV = [
    "EMAIL_SMTP_HOST",
    "EMAIL_SMTP_PORT",
    "EMAIL_ADDRESS",
    "EMAIL_AUTH_CODE",
    "EMAIL_TO",
]


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise EmailConfigError(f"missing required environment variable: {name}")
    return value


def validate_email_environment() -> dict[str, str]:
    values = {name: _required_env(name) for name in REQUIRED_EMAIL_ENV}
    if values["EMAIL_SMTP_PORT"] != "465":
        raise EmailConfigError("EMAIL_SMTP_PORT must be 465 for NetEase SMTP_SSL")
    if values["EMAIL_SMTP_HOST"] != "smtp.163.com":
        LOGGER.warning("EMAIL_SMTP_HOST is %s, expected smtp.163.com for NetEase", values["EMAIL_SMTP_HOST"])
    return values


def build_message(subject: str, html: str, plain_text: str) -> EmailMessage:
    sender = _required_env("EMAIL_ADDRESS")
    recipient = _required_env("EMAIL_TO")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(plain_text)
    message.add_alternative(html, subtype="html")
    return message


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
def send_email(subject: str, html: str, plain_text: str) -> str:
    env = validate_email_environment()
    host = env["EMAIL_SMTP_HOST"]
    port = int(env["EMAIL_SMTP_PORT"])
    sender = env["EMAIL_ADDRESS"]
    auth_code = env["EMAIL_AUTH_CODE"]
    recipient = env["EMAIL_TO"]
    message = build_message(subject, html, plain_text)

    LOGGER.info("Sending email to %s via %s:%s", recipient, host, port)
    with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
        smtp.login(sender, auth_code)
        smtp.send_message(message)
    LOGGER.info("Email delivered to %s", recipient)
    return recipient
