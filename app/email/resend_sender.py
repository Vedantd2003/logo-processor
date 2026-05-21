import base64
import httpx
from pathlib import Path

from .sender import EmailSender


class ResendSender(EmailSender):
    API_URL = "https://api.resend.com/emails"

    def __init__(self, api_key: str, from_address: str) -> None:
        self.api_key = api_key
        self.from_address = from_address

    def send(self, to: str, subject: str, body: str, attachments: list[Path]) -> None:
        encoded_attachments = []
        for path in attachments:
            with open(path, "rb") as f:
                content = base64.b64encode(f.read()).decode()
            encoded_attachments.append({"filename": path.name, "content": content})

        payload = {
            "from": self.from_address,
            "to": [to],
            "subject": subject,
            "text": body,
            "attachments": encoded_attachments,
        }

        response = httpx.post(
            self.API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30,
        )
        response.raise_for_status()
