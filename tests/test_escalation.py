"""Escalation to the owner and the owner's reply going back to the client."""

import pytest
from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import SendMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Escalation, EscalationStatus, Role
from app.services.conversations import get_history, save_message
from app.services.escalations import create_escalation
from bot.handlers import build_router, client, owner
from tests.conftest import OWNER_CHAT_ID
from tests.fakes import FakeLLM, answered_text, make_bot, make_message

ALICE, BOB = 11, 22


def forbidden() -> TelegramForbiddenError:
    return TelegramForbiddenError(
        method=SendMessage(chat_id=1, text="x"), message="Forbidden: bot was blocked"
    )


async def test_escalated_question_goes_to_the_owner(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(client, "ask_llm", FakeLLM("[ESCALATE]"))
    tg_bot = make_bot(sent_message_id=500)
    message = make_message(ALICE, "Можно скидку 30%?", username="alice")

    await client.question(message, session=session, bot=tg_bot, system_prompt="SYS")

    owner_chat, owner_text = tg_bot.send_message.call_args.args
    assert owner_chat == OWNER_CHAT_ID
    assert "Можно скидку 30%?" in owner_text
    assert "@alice" in owner_text
    escalation = await session.scalar(select(Escalation))
    assert (escalation.chat_id, escalation.owner_message_id) == (ALICE, 500)
    assert escalation.status is EscalationStatus.open
    assert answered_text(message) == client.ESCALATED
    assert "[ESCALATE]" not in answered_text(message)


async def test_unreachable_owner_means_no_promise_to_the_client(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(client, "ask_llm", FakeLLM("[ESCALATE]"))
    tg_bot = make_bot()
    tg_bot.send_message.side_effect = forbidden()
    message = make_message(ALICE, "Перенесите мою запись")

    await client.question(message, session=session, bot=tg_bot, system_prompt="SYS")

    assert answered_text(message) == client.FALLBACK
    assert await session.scalar(select(Escalation)) is None


async def test_owner_reply_reaches_the_right_client(session: AsyncSession) -> None:
    await save_message(session, ALICE, Role.user, "Можно скидку?")
    await save_message(session, BOB, Role.user, "Хочу пожаловаться")
    await create_escalation(session, ALICE, "Можно скидку?", owner_message_id=500)
    bobs = await create_escalation(session, BOB, "Хочу пожаловаться", owner_message_id=501)
    tg_bot = make_bot()
    reply = make_message(OWNER_CHAT_ID, "Извините, разберёмся", reply_to=501)

    await owner.owner_reply(reply, session=session, bot=tg_bot)

    chat_id, text = tg_bot.send_message.call_args.args
    assert chat_id == BOB
    assert "Извините, разберёмся" in text
    await session.refresh(bobs)
    assert bobs.status is EscalationStatus.answered
    assert answered_text(reply) == owner.SENT
    # The answer is part of Bob's context now, and only Bob's.
    assert (await get_history(session, BOB))[-1].text == "Извините, разберёмся"
    assert (await get_history(session, ALICE))[-1].text == "Можно скидку?"


async def test_alice_escalation_stays_open(session: AsyncSession) -> None:
    alices = await create_escalation(session, ALICE, "Можно скидку?", owner_message_id=500)
    await create_escalation(session, BOB, "Жалоба", owner_message_id=501)

    await owner.owner_reply(
        make_message(OWNER_CHAT_ID, "Ответ Бобу", reply_to=501), session=session, bot=make_bot()
    )

    await session.refresh(alices)
    assert alices.status is EscalationStatus.open


async def test_reply_to_something_else_is_not_relayed(session: AsyncSession) -> None:
    tg_bot = make_bot()
    reply = make_message(OWNER_CHAT_ID, "Привет", reply_to=999)

    await owner.owner_reply(reply, session=session, bot=tg_bot)

    tg_bot.send_message.assert_not_called()
    assert answered_text(reply) == owner.NOT_AN_ESCALATION


async def test_blocked_client_keeps_escalation_open(session: AsyncSession) -> None:
    escalation = await create_escalation(session, ALICE, "Вопрос", owner_message_id=500)
    tg_bot = make_bot()
    tg_bot.send_message.side_effect = forbidden()
    reply = make_message(OWNER_CHAT_ID, "Ответ", reply_to=500)

    await owner.owner_reply(reply, session=session, bot=tg_bot)

    await session.refresh(escalation)
    assert escalation.status is EscalationStatus.open
    assert answered_text(reply) == owner.SEND_FAILED


async def test_owner_chat_is_routed_to_owner_handlers_first() -> None:
    is_owner = owner.IsOwner()

    assert await is_owner(make_message(OWNER_CHAT_ID, "hi")) is True
    assert await is_owner(make_message(ALICE, "hi")) is False
    assert [r.name for r in build_router().sub_routers] == ["owner", "client"]
