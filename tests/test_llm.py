"""LLM client: real `ask_llm`, fake AsyncOpenAI underneath. No network."""

import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx2
import openai
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.models import ChatMessage, Role
from bot import llm
from bot.handlers import client
from bot.main import missing_settings
from tests.fakes import answered_text, make_bot, make_message

ALICE = 11
REQUEST = httpx2.Request("POST", "https://llm.example/v1/chat/completions")


def completion(content: str | None) -> Any:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.fixture
def create(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """`chat.completions.create` of the client `ask_llm` uses."""
    create = AsyncMock()
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(llm, "get_client", lambda: fake_client)
    return create


async def test_answer_comes_from_the_configured_model(create: AsyncMock) -> None:
    create.return_value = completion("  Стрижка — 2 500 ₽.  ")
    messages = [{"role": "system", "content": "SYS"}, {"role": "user", "content": "Цена?"}]

    assert await llm.ask_llm(messages) == "Стрижка — 2 500 ₽."
    assert create.call_args.kwargs["model"] == "test-model"
    assert create.call_args.kwargs["messages"] == messages


@pytest.mark.parametrize(
    ("disable", "extra_body"),
    [(False, None), (True, {"reasoning": {"enabled": False}})],
    ids=["default", "disabled"],
)
async def test_reasoning_is_switched_off_only_when_asked(
    create: AsyncMock, disable: bool, extra_body: dict[str, Any] | None
) -> None:
    settings.llm_disable_reasoning = disable
    create.return_value = completion("Да.")

    await llm.ask_llm([{"role": "user", "content": "Работаете сегодня?"}])

    assert create.call_args.kwargs["extra_body"] == extra_body


def test_reasoning_stays_on_by_default() -> None:
    assert Settings.model_fields["llm_disable_reasoning"].default is False


@pytest.mark.parametrize(
    "error",
    [
        openai.APITimeoutError(request=REQUEST),
        openai.APIConnectionError(request=REQUEST),
        openai.OpenAIError("401 invalid api key"),
    ],
    ids=["timeout", "connection", "api"],
)
async def test_llm_error_gives_the_client_the_fallback(
    session: AsyncSession,
    create: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    create.side_effect = error
    message = make_message(ALICE, "Сколько стоит стрижка?")

    with caplog.at_level(logging.ERROR):
        await client.question(message, session=session, bot=make_bot(), system_prompt="SYS")

    assert answered_text(message) == client.FALLBACK
    assert message.answer.call_args.kwargs["reply_markup"].inline_keyboard[0][0].text == "Записаться"
    assert "LLM failed" in caplog.text
    # No made-up answer lands in the history.
    roles = (await session.scalars(select(ChatMessage.role))).all()
    assert roles == [Role.user]


async def test_empty_completion_is_an_error_too(session: AsyncSession, create: AsyncMock) -> None:
    create.return_value = completion("   ")
    message = make_message(ALICE, "Привет")

    await client.question(message, session=session, bot=make_bot(), system_prompt="SYS")

    assert answered_text(message) == client.FALLBACK


def test_client_is_built_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "_client", None)
    settings.llm_base_url = "https://llm.example/v1"
    settings.llm_timeout = 12.5

    built = llm.get_client()

    assert str(built.base_url).startswith("https://llm.example/v1")
    assert built.timeout == 12.5
    assert built.api_key == "test-key"
    monkeypatch.setattr(llm, "_client", None)


def test_startup_names_missing_settings() -> None:
    settings.telegram_bot_token = ""
    settings.llm_api_key = ""

    assert missing_settings() == ["TELEGRAM_BOT_TOKEN", "LLM_API_KEY"]
