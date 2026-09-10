"""Small email-delivery boundary with production SMTP and test fakes."""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from backend.api.settings import Settings

logger = logging.getLogger("novaq.email")


class EmailDeliveryError(RuntimeError):
    """Safe boundary exception; underlying SMTP details stay server-side."""


class EmailSender(Protocol):
    def send(self, *, to: str, subject: str, text: str) -> None: ...


@dataclass(frozen=True)
class SentEmail:
    to: str
    subject: str
    text: str


class FakeEmailSender:
    def __init__(self) -> None:
        self.messages: list[SentEmail] = []

    def send(self, *, to: str, subject: str, text: str) -> None:
        self.messages.append(SentEmail(to=to, subject=subject, text=text))


class SmtpEmailSender:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, *, to: str, subject: str, text: str) -> None:
        message = EmailMessage()
        message["From"] = self.settings.smtp_from_email
        message["To"] = to
        message["Subject"] = subject
        message.set_content(text)
        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=15) as smtp:
                if self.settings.smtp_use_tls:
                    smtp.starttls()
                if self.settings.smtp_username:
                    smtp.login(self.settings.smtp_username, self.settings.smtp_password or "")
                smtp.send_message(message)
        except Exception as exc:
            raise EmailDeliveryError("Email delivery failed.") from exc


class ConsoleEmailSender:
    """Local-only sender; production settings reject this mode."""

    def send(self, *, to: str, subject: str, text: str) -> None:
        logger.warning("LOCAL EMAIL to=%s subject=%s\n%s", to, subject, text)


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.email_delivery_mode == "smtp":
        return SmtpEmailSender(settings)
    return ConsoleEmailSender()


def verification_email(public_url: str, raw_token: str) -> tuple[str, str]:
    link = f"{public_url.rstrip('/')}/verify-email#token={raw_token}"
    return "Verify your NovaQ email", f"Verify your NovaQ email within the next hour:\n\n{link}\n"


def reset_email(public_url: str, raw_token: str) -> tuple[str, str]:
    link = f"{public_url.rstrip('/')}/reset-password#token={raw_token}"
    return "Reset your NovaQ password", f"Reset your NovaQ password within the next 30 minutes:\n\n{link}\n"
