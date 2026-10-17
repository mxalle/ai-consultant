"""/stats: clients and messages today / over 7 days, open escalations."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage, EscalationStatus, Role
from app.services.conversations import get_or_create_conversation
from app.services.escalations import create_escalation
from app.services.stats import PeriodStats, get_stats
from bot.handlers import owner

MOSCOW = ZoneInfo("Europe/Moscow")
# 15:00 in Moscow; Moscow midnight is 2026-10-16 21:00 UTC.
NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


async def add(session: AsyncSession, chat_id: int, at: datetime, role: Role = Role.user) -> None:
    conversation = await get_or_create_conversation(session, chat_id)
    session.add(ChatMessage(conversation_id=conversation.id, role=role, text="…", created_at=at))
    await session.commit()


async def test_today_and_week(session: AsyncSession) -> None:
    await add(session, 1, NOW - timedelta(hours=1))
    await add(session, 1, NOW - timedelta(hours=1), role=Role.assistant)
    await add(session, 1, NOW - timedelta(minutes=5))
    # 01:00 Moscow today, still yesterday in UTC.
    await add(session, 2, datetime(2026, 10, 16, 22, 0, tzinfo=UTC))
    # 23:30 Moscow yesterday.
    await add(session, 3, datetime(2026, 10, 16, 20, 30, tzinfo=UTC))
    await add(session, 4, NOW - timedelta(days=5))
    await add(session, 5, NOW - timedelta(days=8))

    stats = await get_stats(session, MOSCOW, now=NOW)

    assert stats.today == PeriodStats(clients=2, messages=3)
    assert stats.week == PeriodStats(clients=4, messages=5)


async def test_open_escalations(session: AsyncSession) -> None:
    await create_escalation(session, 1, "скидка?", owner_message_id=1)
    await create_escalation(session, 2, "жалоба", owner_message_id=2)
    answered = await create_escalation(session, 3, "перенос", owner_message_id=3)
    answered.status = EscalationStatus.answered
    await session.commit()

    stats = await get_stats(session, MOSCOW, now=NOW)

    assert stats.open_escalations == 2


async def test_empty_database(session: AsyncSession) -> None:
    stats = await get_stats(session, MOSCOW, now=NOW)

    assert stats.today == stats.week == PeriodStats(clients=0, messages=0)
    assert stats.open_escalations == 0


async def test_stats_text_shows_the_numbers(session: AsyncSession) -> None:
    await add(session, 1, NOW - timedelta(days=2))
    await create_escalation(session, 1, "скидка?", owner_message_id=1)

    text = owner.format_stats(await get_stats(session, MOSCOW, now=NOW))

    assert "Барбершоп «Тест»" in text
    assert "За 7 дней:\n• клиентов: 1\n• сообщений от клиентов: 1" in text
    assert "Вопросов ждут вашего ответа: 1" in text
