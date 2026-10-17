import enum
from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Role(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class EscalationStatus(str, enum.Enum):
    open = "open"
    answered = "answered"


role_enum = Enum(
    Role,
    name="message_role",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)

escalation_status_enum = Enum(
    EscalationStatus,
    name="escalation_status",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class Conversation(Base):
    """One per client chat."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    """A client message or a bot/owner answer to it.

    `/reset` only sets `archived`: the row stays for the rate limit and /stats,
    it just no longer goes to the LLM as context.
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[Role] = mapped_column(role_enum)
    text: Mapped[str] = mapped_column(Text)
    archived: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), index=True
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Escalation(Base):
    """A client question handed over to the owner.

    `owner_message_id` is the bot's message in the owner chat; the owner
    replies to it, and that reply is how we find the client again.
    """

    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    question: Mapped[str] = mapped_column(Text)
    owner_message_id: Mapped[int] = mapped_column(BigInteger, index=True)
    status: Mapped[EscalationStatus] = mapped_column(
        escalation_status_enum,
        default=EscalationStatus.open,
        server_default=EscalationStatus.open.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
