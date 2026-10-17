"""Per-client rate limit, counted straight from the messages table."""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage, Conversation, Role, utcnow

WINDOW = timedelta(hours=1)


async def is_rate_limited(
    session: AsyncSession, chat_id: int, limit: int, now: datetime | None = None
) -> bool:
    """True once the client has sent `limit` messages within the last hour.

    Archived messages count too, so `/reset` does not lift the limit. Refused
    messages are not stored, so the limit lifts by itself as the hour rolls on.
    """
    since = (now or utcnow()) - WINDOW
    count = await session.scalar(
        select(func.count())
        .select_from(ChatMessage)
        .join(Conversation)
        .where(
            Conversation.chat_id == chat_id,
            ChatMessage.role == Role.user,
            ChatMessage.created_at >= since,
        )
    )
    return count >= limit
