from pydantic import BaseModel
from typing import Literal


class ProcessResponse(BaseModel):
    request_id: str
    silhouette: Literal["generated", "failed"]
    border: Literal["generated", "failed"]
    grayscale: Literal["generated", "failed"]
    email_status: Literal["sent", "failed"]
    sent_to: str = ""
    message: str = ""
    images: dict[str, str] = {}


class HealthResponse(BaseModel):
    status: Literal["ok"]
