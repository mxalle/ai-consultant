from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # `OWNER_CHAT_ID=` left blank in .env means "not set", not a parse error.
        env_ignore_empty=True,
    )

    debug: bool = False

    database_url: str = "postgresql+asyncpg://consultant:consultant@localhost:5433/consultant"

    # Telegram. Empty defaults so tests and alembic run without them; the bot
    # itself refuses to start until they are set (see bot/main.py).
    telegram_bot_token: str = ""
    # Where questions the bot cannot answer go. Usually the owner's own user id,
    # a group id (negative) works too.
    owner_chat_id: int = 0
    # "Today" in /stats is counted in this timezone.
    bot_timezone: str = "Europe/Moscow"

    # The business the bot speaks for.
    business_name: str = ""
    # Online booking page (YCLIENTS, DIKIDI...) behind the «Записаться» button.
    booking_url: str = ""
    # Plain-text knowledge base, read once at startup and put into the prompt whole.
    knowledge_file: str = "knowledge/demo_barbershop.md"

    # Any OpenAI-compatible endpoint: OpenRouter, YandexGPT, a local proxy...
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    llm_model: str = ""
    # Seconds to wait for one completion before the client gets the fallback text.
    llm_timeout: float = 30.0

    # Client messages per rolling hour before the bot politely stops answering.
    rate_limit_per_hour: int = 30


settings = Settings()
