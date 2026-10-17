"""Client chat history: what goes to the LLM as context."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage, Conversation, Role

# How many recent messages of one client the LLM sees.
HISTORY_LIMIT = 10


async def get_or_create_conversation(
    session: AsyncSession, chat_id: int, username: str | None = None
) -> Conversation:
    conversation = await session.scalar(
        select(Conversation).where(Conversation.chat_id == chat_id)
    )
    if conversation is None:
        conversation = Conversation(chat_id=chat_id, username=username)
        session.add(conversation)
        await session.flush()
    elif username and conversation.username != username:
        conversation.username = username
    return conversation


async def save_message(
    session: AsyncSession,
    chat_id: int,
    role: Role,
    text: str,
    username: str | None = None,
) -> ChatMessage:
    conversation = await get_or_create_conversation(session, chat_id, username)
    message = ChatMessage(conversation_id=conversation.id, role=role, text=text)
    session.add(message)
    await session.commit()
    return message


async def get_history(
    session: AsyncSession, chat_id: int, limit: int = HISTORY_LIMIT
) -> list[ChatMessage]:
    """The last `limit` messages of this client, oldest first, without archived ones."""
    rows = await session.scalars(
        select(ChatMessage)
        .join(Conversation)
        .where(Conversation.chat_id == chat_id, ChatMessage.archived.is_(False))
        .order_by(ChatMessage.id.desc())
        .limit(limit)
    )
    return list(reversed(rows.all()))


async def clear_history(session: AsyncSession, chat_id: int) -> None:
    """`/reset`: hide the history from the LLM. Rows stay for the rate limit and /stats."""
    await session.execute(
        update(ChatMessage)
        .where(
            ChatMessage.conversation_id.in_(
                select(Conversation.id).where(Conversation.chat_id == chat_id)
            )
        )
        .values(archived=True)
    )
    await session.commit()
