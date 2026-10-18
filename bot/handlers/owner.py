"""The owner's chat (OWNER_CHAT_ID): escalated questions in, answers out.

Nothing here goes through the LLM. The owner either replies to an escalated
question or uses a command.
"""

import logging
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart, Filter
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.escalations import (
    create_escalation,
    get_escalation_by_owner_message,
    mark_answered,
)
from app.services.stats import Stats, get_stats

logger = logging.getLogger(__name__)

OWNER_HELP = (
    "Чат владельца: {business_name}.\n\n"
    "Сюда приходят вопросы клиентов, на которые бот не нашёл ответа в базе "
    "знаний. Чтобы ответить клиенту, ответьте (reply) на сообщение с вопросом — "
    "бот перешлёт ваш ответ.\n\n"
    "/stats — сколько клиентов написали боту."
)
STATS = (
    "📊 {business_name}: бот в цифрах\n\n"
    "Сегодня:\n"
    "• клиентов: {today_clients}\n"
    "• сообщений от клиентов: {today_messages}\n\n"
    "За 7 дней:\n"
    "• клиентов: {week_clients}\n"
    "• сообщений от клиентов: {week_messages}\n\n"
    "Вопросов ждут вашего ответа: {open_escalations}"
)
QUESTION_FOR_OWNER = (
    "❓ Вопрос от клиента {who}:\n\n"
    "{question}\n\n"
    "Ответьте на это сообщение (reply) — я перешлю ответ клиенту."
)
ANSWER_FOR_CLIENT = "Ответ администратора:\n\n{text}"
SENT = "✅ Отправил клиенту."
SEND_FAILED = "Не получилось отправить ответ клиенту — возможно, он заблокировал бота."
NOT_AN_ESCALATION = (
    "Не понял, какому клиенту это отправить. Ответьте (reply) именно на "
    "сообщение с вопросом клиента."
)


class IsOwner(Filter):
    """Messages from OWNER_CHAT_ID. Read at call time, so tests can change it."""

    async def __call__(self, message: Message) -> bool:
        return message.chat.id == settings.owner_chat_id


router = Router(name="owner")
router.message.filter(IsOwner())


async def forward_to_owner(
    session: AsyncSession, bot: Bot, chat_id: int, username: str | None, question: str
) -> bool:
    """Send a client's question to the owner and remember it as an escalation.

    False when the owner chat cannot be reached (e.g. the owner never pressed
    /start), so the caller does not promise the client an answer.
    """
    who = f"@{username}" if username else "без username"
    try:
        sent = await bot.send_message(
            settings.owner_chat_id,
            QUESTION_FOR_OWNER.format(who=f"{who} (id {chat_id})", question=question),
        )
    except TelegramAPIError:
        logger.exception("cannot reach owner chat %s", settings.owner_chat_id)
        return False
    await create_escalation(session, chat_id, question, sent.message_id)
    logger.info("escalated chat_id=%s as owner message %s", chat_id, sent.message_id)
    return True


@router.message(CommandStart())
async def owner_start(message: Message) -> None:
    await message.answer(OWNER_HELP.format(business_name=settings.business_name))


@router.message(Command("stats"))
async def stats(message: Message, session: AsyncSession) -> None:
    result = await get_stats(session, ZoneInfo(settings.bot_timezone))
    await message.answer(format_stats(result))


def format_stats(stats: Stats) -> str:
    return STATS.format(
        business_name=settings.business_name,
        today_clients=stats.today.clients,
        today_messages=stats.today.messages,
        week_clients=stats.week.clients,
        week_messages=stats.week.messages,
        open_escalations=stats.open_escalations,
    )


@router.message(F.text, F.reply_to_message)
async def owner_reply(message: Message, session: AsyncSession, bot: Bot) -> None:
    """The owner replied to an escalated question: relay the answer to the client."""
    escalation = await get_escalation_by_owner_message(
        session, message.reply_to_message.message_id
    )
    if escalation is None:
        await message.answer(NOT_AN_ESCALATION)
        return

    try:
        await bot.send_message(
            escalation.chat_id,
            ANSWER_FOR_CLIENT.format(text=message.text),
        )
    except TelegramAPIError:
        logger.exception("cannot deliver owner answer to chat_id=%s", escalation.chat_id)
        await message.answer(SEND_FAILED)
        return

    await mark_answered(session, escalation, message.text)
    logger.info("escalation %s answered", escalation.id)
    await message.answer(SENT)


@router.message()
async def owner_other(message: Message) -> None:
    await message.answer(OWNER_HELP.format(business_name=settings.business_name))
