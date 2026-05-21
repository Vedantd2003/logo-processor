import base64
import httpx
from pathlib import Path

from .sender import EmailSender

_API_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoSender(EmailSender):
    """Brevo transactional email via REST API — works from any cloud host."""

    def __init__(self, login: str, api_key: str) -> None:
        self.login = login    # verified sender email in Brevo account
        self.api_key = api_key  # xkeysib-... API key

    def send(self, to: str, subject: str, body: str, attachments: list[Path]) -> None:
        encoded = []
        for path in attachments:
            encoded.append({
                "content": base64.b64encode(path.read_bytes()).decode(),
                "name": path.name,
            })

        payload = {
            "sender": {"email": self.login, "name": "Logo Processor"},
            "to": [{"email": to}],
            "subject": subject,
            "textContent": body,
            "attachment": encoded,
        }

        response = httpx.post(
            _API_URL,
            json=payload,
            headers={"api-key": self.api_key, "Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
