"""Questions handed over to the owner, and the owner's answers to them."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Escalation, EscalationStatus, Role
from app.services.conversations import save_message


async def create_escalation(
    session: AsyncSession, chat_id: int, question: str, owner_message_id: int
) -> Escalation:
    escalation = Escalation(
        chat_id=chat_id, question=question, owner_message_id=owner_message_id
    )
    session.add(escalation)
    await session.commit()
    return escalation


async def get_escalation_by_owner_message(
    session: AsyncSession, owner_message_id: int
) -> Escalation | None:
    """The escalation the owner is replying to, found by the bot's message id."""
    return await session.scalar(
        select(Escalation)
        .where(Escalation.owner_message_id == owner_message_id)
        .order_by(Escalation.id.desc())
        .limit(1)
    )


async def mark_answered(session: AsyncSession, escalation: Escalation, answer: str) -> None:
    """Close the escalation and put the owner's answer into the client's history,
    so the LLM knows what the client was told."""
    escalation.status = EscalationStatus.answered
    await save_message(session, escalation.chat_id, Role.assistant, answer)
