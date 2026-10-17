"""Bot entrypoint: `python -m bot.main`.

Long polling, one process, talks to Postgres through `app.database.session_factory`.
The knowledge base is read once here; edit the file and restart to change it.
"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramAPIError, TelegramUnauthorizedError
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from app.config import settings
from app.database import engine, session_factory
from bot.handlers import build_router
from bot.middlewares import DbSessionMiddleware
from bot.prompt import build_system_prompt, load_knowledge

logger = logging.getLogger("bot")

COMMANDS = [
    BotCommand(command="start", description="Начать"),
    BotCommand(command="reset", description="Очистить историю переписки"),
]
# Replaces the default menu in the owner chat.
OWNER_COMMANDS = [
    BotCommand(command="start", description="Как отвечать клиентам"),
    BotCommand(command="stats", description="Статистика бота"),
]


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    # httpx logs every Telegram poll at INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def missing_settings() -> list[str]:
    """Names of required .env values that are still empty."""
    required = {
        "TELEGRAM_BOT_TOKEN": settings.telegram_bot_token,
        "OWNER_CHAT_ID": settings.owner_chat_id,
        "BUSINESS_NAME": settings.business_name,
        "BOOKING_URL": settings.booking_url,
        "KNOWLEDGE_FILE": settings.knowledge_file,
        "LLM_BASE_URL": settings.llm_base_url,
        "LLM_API_KEY": settings.llm_api_key,
        "LLM_MODEL": settings.llm_model,
    }
    return [name for name, value in required.items() if not value]


def build_dispatcher() -> Dispatcher:
    """Dispatcher wired to the shared database session factory."""
    dispatcher = Dispatcher()
    dispatcher.update.middleware(DbSessionMiddleware(session_factory))
    dispatcher.include_router(build_router())
    return dispatcher


async def run() -> None:
    missing = missing_settings()
    if missing:
        raise SystemExit(
            f"not set in .env: {', '.join(missing)} (see .env.example)"
        )
    try:
        knowledge = load_knowledge(settings.knowledge_file)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read KNOWLEDGE_FILE: {exc}") from exc
    system_prompt = build_system_prompt(settings.business_name, knowledge)

    # No default parse_mode: everything the bot sends is plain text, because it
    # is either model output or client text relayed to the owner.
    bot = Bot(token=settings.telegram_bot_token, default=DefaultBotProperties())
    dispatcher = build_dispatcher()

    try:
        try:
            me = await bot.get_me()
        except TelegramUnauthorizedError:
            raise SystemExit("Telegram rejected TELEGRAM_BOT_TOKEN — check it in @BotFather.")
        logger.info(
            "starting as @%s (id=%s) for %r, knowledge %s (%d chars), model %s",
            me.username,
            me.id,
            settings.business_name,
            settings.knowledge_file,
            len(knowledge),
            settings.llm_model,
        )

        await bot.set_my_commands(COMMANDS, scope=BotCommandScopeDefault())
        try:
            await bot.set_my_commands(
                OWNER_COMMANDS,
                scope=BotCommandScopeChat(chat_id=settings.owner_chat_id),
            )
        except TelegramAPIError as exc:
            # Telegram does not know the chat until the owner writes to the bot.
            logger.warning(
                "owner chat %s not reachable yet (%s) — the owner should send "
                "/start to the bot, otherwise escalations cannot be delivered",
                settings.owner_chat_id,
                exc,
            )
        await dispatcher.start_polling(bot, system_prompt=system_prompt)
    finally:
        await bot.session.close()
        await engine.dispose()


def main() -> None:
    setup_logging()
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit) as exc:
        if isinstance(exc, SystemExit) and exc.code:
            logger.error("%s", exc.code)
            sys.exit(1)
        logger.info("bot stopped")


if __name__ == "__main__":
    main()
