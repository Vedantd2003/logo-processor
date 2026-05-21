from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    recipient_email: str = Field(..., description="Email address to receive processed outputs")
    email_provider: str = Field("smtp", description="Email provider: 'smtp' or 'resend'")

    smtp_host: str = Field("smtp.gmail.com")
    smtp_port: int = Field(465)
    smtp_user: str = Field("")
    smtp_password: str = Field("")

    resend_api_key: str = Field("")
    resend_from: str = Field("onboarding@resend.dev")

    max_upload_mb: int = Field(5)
    log_level: str = Field("INFO")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
