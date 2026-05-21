import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from .sender import EmailSender

BREVO_HOST = "smtp-relay.brevo.com"
BREVO_PORT = 587


class BrevoSender(EmailSender):
    """Brevo (Sendinblue) SMTP relay — works from all cloud hosts."""

    def __init__(self, login: str, smtp_key: str) -> None:
        self.login = login      # your Brevo account email
        self.smtp_key = smtp_key  # SMTP key from Brevo dashboard

    def send(self, to: str, subject: str, body: str, attachments: list[Path]) -> None:
        msg = EmailMessage()
        msg["From"] = self.login
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        for path in attachments:
            with open(path, "rb") as f:
                msg.add_attachment(
                    f.read(),
                    maintype="image",
                    subtype="png",
                    filename=path.name,
                )

        ctx = ssl.create_default_context()
        with smtplib.SMTP(BREVO_HOST, BREVO_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
            server.login(self.login, self.smtp_key)
            server.send_message(msg)
