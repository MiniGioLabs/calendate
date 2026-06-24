"""Configuration."""

from __future__ import annotations
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "CalDate"
    SECRET_KEY: str = "replace-me"
    BASE_URL: str = "http://localhost:8000"
    DATABASE_PATH: str = ""
    TEMPLATES_DIR: str = ""
    STATIC_DIR: str = ""
    STRIPE_SECRET_KEY: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""

    @property
    def twilio_configured(self) -> bool:
        return bool(self.TWILIO_ACCOUNT_SID and self.TWILIO_AUTH_TOKEN)

    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()
