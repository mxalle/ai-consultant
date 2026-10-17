"""Numbers for the owner's /stats: how much the bot actually talks to clients."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage, Escalation, EscalationStatus, Role, utcnow


@dataclass
class PeriodStats:
    clients: int
    messages: int


@dataclass
class Stats:
    today: PeriodStats
    week: PeriodStats
    open_escalations: int


async def _period(session: AsyncSession, since: datetime) -> PeriodStats:
    """Clients who wrote and messages they sent since `since` (bot answers excluded)."""
    row = (
        await session.execute(
            select(
                func.count(distinct(ChatMessage.conversation_id)), func.count()
            ).where(ChatMessage.role == Role.user, ChatMessage.created_at >= since)
        )
    ).one()
    return PeriodStats(clients=row[0], messages=row[1])


async def get_stats(
    session: AsyncSession, tz: ZoneInfo, now: datetime | None = None
) -> Stats:
    """Today starts at local midnight in `tz`; the week is today plus six days before."""
    local_now = (now or utcnow()).astimezone(tz)
    today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=6)

    open_escalations = await session.scalar(
        select(func.count())
        .select_from(Escalation)
        .where(Escalation.status == EscalationStatus.open)
    )
    return Stats(
        today=await _period(session, today_start.astimezone(UTC)),
        week=await _period(session, week_start.astimezone(UTC)),
        open_escalations=open_escalations,
    )
