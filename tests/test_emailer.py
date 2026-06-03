import pytest

from thinktank_digest.emailer import EmailConfigError, build_message, send_email, validate_email_environment


def test_build_message_uses_environment_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMAIL_ADDRESS", "sender@163.com")
    monkeypatch.setenv("EMAIL_TO", "recipient@example.com")

    message = build_message("subject", "<p>html</p>", "plain")

    assert message["From"] == "sender@163.com"
    assert message["To"] == "recipient@example.com"
    assert message.is_multipart()


def test_build_message_requires_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMAIL_ADDRESS", raising=False)
    monkeypatch.setenv("EMAIL_TO", "recipient@example.com")

    with pytest.raises(EmailConfigError):
        build_message("subject", "<p>html</p>", "plain")


def test_validate_email_environment_requires_netease_ssl_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMAIL_SMTP_HOST", "smtp.163.com")
    monkeypatch.setenv("EMAIL_SMTP_PORT", "25")
    monkeypatch.setenv("EMAIL_ADDRESS", "sender@163.com")
    monkeypatch.setenv("EMAIL_AUTH_CODE", "auth-code")
    monkeypatch.setenv("EMAIL_TO", "recipient@example.com")

    with pytest.raises(EmailConfigError):
        validate_email_environment()


def test_send_email_uses_smtp_ssl(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, sender, auth_code):
            calls.append(("login", sender, auth_code))

        def send_message(self, message):
            calls.append(("send_message", message["To"], message.is_multipart()))

    monkeypatch.setenv("EMAIL_SMTP_HOST", "smtp.163.com")
    monkeypatch.setenv("EMAIL_SMTP_PORT", "465")
    monkeypatch.setenv("EMAIL_ADDRESS", "sender@163.com")
    monkeypatch.setenv("EMAIL_AUTH_CODE", "auth-code")
    monkeypatch.setenv("EMAIL_TO", "recipient@example.com")
    monkeypatch.setattr("smtplib.SMTP_SSL", FakeSMTP)

    recipient = send_email("subject", "<p>html</p>", "plain")

    assert recipient == "recipient@example.com"
    assert calls[0] == ("connect", "smtp.163.com", 465, 30)
    assert ("login", "sender@163.com", "auth-code") in calls
    assert ("send_message", "recipient@example.com", True) in calls
