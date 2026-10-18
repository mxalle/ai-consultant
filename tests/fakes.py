"""Stand-ins for aiogram objects, so handlers can be called as plain functions."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock


def make_message(
    chat_id: int,
    text: str | None = None,
    *,
    username: str | None = "client",
    reply_to: int | None = None,
    chat_type: str = "private",
) -> Any:
    """A Message with just the fields the handlers read; `answer` is recorded."""
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id, type=chat_type),
        from_user=SimpleNamespace(id=chat_id, username=username),
        text=text,
        reply_to_message=SimpleNamespace(message_id=reply_to) if reply_to else None,
        answer=AsyncMock(),
    )


def make_bot(sent_message_id: int = 500) -> Any:
    """A Bot whose `send_message` returns a message with `sent_message_id`."""
    bot = AsyncMock()
    bot.send_message.return_value = SimpleNamespace(message_id=sent_message_id)
    return bot


def answered_text(message: Any) -> str:
    """Text of the last `message.answer(...)` call."""
    args, kwargs = message.answer.call_args
    return args[0] if args else kwargs["text"]


def has_booking_button(message: Any) -> bool:
    """Whether the last `message.answer(...)` carried the «Записаться» button."""
    return message.answer.call_args.kwargs.get("reply_markup") is not None


class FakeLLM:
    """Replaces `ask_llm`: returns canned replies and remembers what it was sent."""

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls: list[list[dict[str, str]]] = []

    async def __call__(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        return self.replies.pop(0)
