from pydantic import BaseModel
from typing import Literal


class ProcessResponse(BaseModel):
    request_id: str
    silhouette: Literal["generated", "failed"]
    border: Literal["generated", "failed"]
    grayscale: Literal["generated", "failed"]
    email_status: str  # "sent", "pending", or "failed: <error detail>"
    message: str = ""
    images: dict[str, str] = {}  # base64-encoded PNG for each output


class HealthResponse(BaseModel):
    status: Literal["ok"]
