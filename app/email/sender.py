from abc import ABC, abstractmethod
from pathlib import Path


class EmailSender(ABC):
    @abstractmethod
    def send(
        self,
        to: str,
        subject: str,
        body: str,
        attachments: list[Path],
    ) -> None:
        """Send email with attachments. Raises on failure."""
