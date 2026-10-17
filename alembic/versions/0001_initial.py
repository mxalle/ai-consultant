"""initial schema: conversations, messages, escalations

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-17 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_conversations_chat_id"), "conversations", ["chat_id"], unique=True
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("user", "assistant", name="message_role"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "archived", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_messages_conversation_id"), "messages", ["conversation_id"]
    )
    op.create_index(op.f("ix_messages_created_at"), "messages", ["created_at"])

    op.create_table(
        "escalations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("owner_message_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "answered", name="escalation_status"),
            server_default="open",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_escalations_chat_id"), "escalations", ["chat_id"])
    op.create_index(
        op.f("ix_escalations_owner_message_id"), "escalations", ["owner_message_id"]
    )


def downgrade() -> None:
    op.drop_table("escalations")
    op.drop_table("messages")
    op.drop_table("conversations")
    sa.Enum(name="escalation_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="message_role").drop(op.get_bind(), checkfirst=True)
