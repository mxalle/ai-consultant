"""Everything a client writes in a private chat with the bot."""

import contextlib
import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction, ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Role
from app.services.conversations import clear_history, get_history, save_message
from bot.keyboards import booking_keyboard
from bot.llm import LLMError, ask_llm
from bot.prompt import parse_reply, truncate

logger = logging.getLogger(__name__)

router = Router(name="client")
router.message.filter(F.chat.type == ChatType.PRIVATE)

GREETING = (
    "Здравствуйте! Это {business_name}.\n\n"
    "Подскажу про услуги и цены, мастеров, адрес и часы работы — просто "
    "напишите вопрос. Записаться можно по кнопке ниже."
)
RESET_DONE = "Начнём сначала: прошлую переписку я забыл. Чем могу помочь?"
FALLBACK = (
    "Сейчас не могу ответить, напишите, пожалуйста, чуть позже "
    "или запишитесь по кнопке."
)
ONLY_TEXT = "Пока понимаю только текст. Напишите, пожалуйста, вопрос словами."
UNKNOWN_COMMAND = "Такой команды нет. Просто напишите свой вопрос — или /start."


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        GREETING.format(business_name=settings.business_name),
        reply_markup=booking_keyboard(),
    )


@router.message(Command("reset"))
async def reset(message: Message, session: AsyncSession) -> None:
    await clear_history(session, message.chat.id)
    await message.answer(RESET_DONE, reply_markup=booking_keyboard())


@router.message(F.text.startswith("/"))
async def unknown_command(message: Message) -> None:
    await message.answer(UNKNOWN_COMMAND)


@router.message(F.text)
async def question(
    message: Message, session: AsyncSession, bot: Bot, system_prompt: str
) -> None:
    """A client question: history + knowledge base -> LLM -> answer."""
    chat_id = message.chat.id
    text = truncate(message.text)
    await save_message(
        session, chat_id, Role.user, text, username=message.from_user.username
    )

    history = await get_history(session, chat_id)
    llm_messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m.role.value, "content": m.text} for m in history
    ]

    with contextlib.suppress(TelegramAPIError):
        await bot.send_chat_action(chat_id, ChatAction.TYPING)

    try:
        raw = await ask_llm(llm_messages)
    except LLMError:
        logger.exception("LLM failed for chat_id=%s", chat_id)
        await message.answer(FALLBACK, reply_markup=booking_keyboard())
        return

    escalate, answer = parse_reply(raw)
    if escalate or not answer:
        answer = FALLBACK

    await save_message(session, chat_id, Role.assistant, answer)
    # Model output is sent as plain text: stray markdown/HTML must not break it.
    await message.answer(answer, parse_mode=None, reply_markup=booking_keyboard())


@router.message()
async def not_text(message: Message) -> None:
    """Photos, voice messages, stickers..."""
    await message.answer(ONLY_TEXT, reply_markup=booking_keyboard())
