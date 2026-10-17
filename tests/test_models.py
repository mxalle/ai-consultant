"""Column defaults the services rely on."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage, Conversation, Escalation, EscalationStatus, Role


async def test_new_rows_get_defaults(session: AsyncSession) -> None:
    conversation = Conversation(chat_id=42, username="ivan")
    session.add(conversation)
    await session.flush()
    message = ChatMessage(conversation_id=conversation.id, role=Role.user, text="Привет")
    escalation = Escalation(chat_id=42, question="Можно скидку?", owner_message_id=7)
    session.add_all([message, escalation])
    await session.commit()

    assert message.archived is False
    assert message.created_at is not None
    assert escalation.status is EscalationStatus.open
    assert escalation.created_at is not None
