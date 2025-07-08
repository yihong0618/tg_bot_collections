from functools import cached_property

import openai
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    telegram_bot_token: str
    timezone: str = "Asia/Shanghai"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    google_gemini_api_key: str | None = None
    anthropic_api_key: str | None = None
    telegra_ph_token: str | None = None

    @cached_property
    def openai_client(self) -> openai.OpenAI:
        return openai.OpenAI(
            api_key=self.openai_api_key,
            base_url=self.openai_base_url,
        )

    @cached_property
    def telegraph_client(self):
        from handlers._telegraph import TelegraphAPI

        return TelegraphAPI(self.telegra_ph_token)


settings = Settings()  # type: ignore
