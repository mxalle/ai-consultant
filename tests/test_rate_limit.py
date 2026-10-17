"""RATE_LIMIT_PER_HOUR: the N+1-th message within an hour gets no LLM call."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ChatMessage, Role, utcnow
from app.services.conversations import clear_history, get_or_create_conversation, save_message
from app.services.rate_limit import is_rate_limited
from bot.handlers import client
from tests.fakes import FakeLLM, answered_text, make_bot, make_message

ALICE, BOB = 11, 22
LIMIT = 3


async def test_limit_hits_on_the_n_plus_first_message(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.rate_limit_per_hour = LIMIT
    llm = FakeLLM(*["Ответ"] * (LIMIT + 1))
    monkeypatch.setattr(client, "ask_llm", llm)

    messages = [make_message(ALICE, f"вопрос {i}") for i in range(LIMIT + 1)]
    for message in messages:
        await client.question(message, session=session, bot=make_bot(), system_prompt="SYS")

    assert [answered_text(m) for m in messages[:LIMIT]] == ["Ответ"] * LIMIT
    assert answered_text(messages[LIMIT]) == client.RATE_LIMITED
    assert len(llm.calls) == LIMIT
    # The refused message is not stored and so does not prolong the limit.
    stored = await session.scalar(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.role == Role.user)
    )
    assert stored == LIMIT


async def test_limit_is_per_client(session: AsyncSession) -> None:
    for i in range(LIMIT):
        await save_message(session, ALICE, Role.user, f"вопрос {i}")

    assert await is_rate_limited(session, ALICE, LIMIT) is True
    assert await is_rate_limited(session, BOB, LIMIT) is False


async def test_only_the_last_hour_counts(session: AsyncSession) -> None:
    conversation = await get_or_create_conversation(session, ALICE)
    old = utcnow() - timedelta(hours=1, minutes=1)
    session.add_all(
        ChatMessage(conversation_id=conversation.id, role=Role.user, text="давно", created_at=old)
        for _ in range(LIMIT)
    )
    await session.commit()

    assert await is_rate_limited(session, ALICE, LIMIT) is False


async def test_bot_answers_do_not_count(session: AsyncSession) -> None:
    for _ in range(LIMIT):
        await save_message(session, ALICE, Role.assistant, "ответ")

    assert await is_rate_limited(session, ALICE, LIMIT) is False


async def test_reset_does_not_lift_the_limit(session: AsyncSession) -> None:
    for i in range(LIMIT):
        await save_message(session, ALICE, Role.user, f"вопрос {i}")

    await clear_history(session, ALICE)

    assert await is_rate_limited(session, ALICE, LIMIT) is True
