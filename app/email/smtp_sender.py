import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from .sender import EmailSender


class SmtpSender(EmailSender):
    def __init__(self, host: str, port: int, user: str, password: str) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password

    def _build_message(self, to: str, subject: str, body: str, attachments: list[Path]) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = self.user
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
        return msg

    def send(self, to: str, subject: str, body: str, attachments: list[Path]) -> None:
        msg = self._build_message(to, subject, body, attachments)
        ctx = ssl.create_default_context()

        if self.port == 465:
            # SMTP over SSL
            with smtplib.SMTP_SSL(self.host, self.port, context=ctx, timeout=30) as server:
                server.login(self.user, self.password)
                server.send_message(msg)
        else:
            # STARTTLS — port 587, works on most cloud hosts including Render
            with smtplib.SMTP(self.host, self.port, timeout=30) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.ehlo()
                server.login(self.user, self.password)
                server.send_message(msg)
