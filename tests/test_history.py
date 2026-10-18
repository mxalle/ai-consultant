"""Chat history: last 10 messages, per client, and what the LLM gets."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Role
from app.services.conversations import (
    HISTORY_LIMIT,
    clear_history,
    get_history,
    save_message,
)
from bot.handlers import client
from bot.prompt import MAX_MESSAGE_LENGTH
from tests.fakes import FakeLLM, answered_text, has_booking_button, make_bot, make_message

ALICE, BOB = 11, 22


async def test_history_is_cut_to_the_last_ten(session: AsyncSession) -> None:
    for i in range(15):
        role = Role.user if i % 2 == 0 else Role.assistant
        await save_message(session, ALICE, role, f"msg {i}")

    history = await get_history(session, ALICE)

    assert HISTORY_LIMIT == 10
    assert [m.text for m in history] == [f"msg {i}" for i in range(5, 15)]


async def test_history_does_not_mix_clients(session: AsyncSession) -> None:
    await save_message(session, ALICE, Role.user, "Алиса 1")
    await save_message(session, BOB, Role.user, "Боб 1")
    await save_message(session, ALICE, Role.user, "Алиса 2")

    assert [m.text for m in await get_history(session, ALICE)] == ["Алиса 1", "Алиса 2"]
    assert [m.text for m in await get_history(session, BOB)] == ["Боб 1"]


async def test_reset_clears_only_own_history(session: AsyncSession) -> None:
    await save_message(session, ALICE, Role.user, "старое")
    await save_message(session, BOB, Role.user, "Боб")

    await clear_history(session, ALICE)
    await save_message(session, ALICE, Role.user, "новое")

    assert [m.text for m in await get_history(session, ALICE)] == ["новое"]
    assert [m.text for m in await get_history(session, BOB)] == ["Боб"]


async def test_username_is_kept_on_the_conversation(session: AsyncSession) -> None:
    message = await save_message(session, ALICE, Role.user, "привет", username="alice")
    await session.refresh(message, ["conversation"])

    assert message.conversation.username == "alice"


async def test_llm_gets_system_prompt_and_this_clients_history(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await save_message(session, BOB, Role.user, "чужой вопрос")
    llm = FakeLLM("Мужская стрижка — 2 500 ₽.", "Стрижка длится 60 минут.")
    monkeypatch.setattr(client, "ask_llm", llm)

    first = make_message(ALICE, "Сколько стоит стрижка?")
    await client.question(first, session=session, bot=make_bot(), system_prompt="SYS")
    second = make_message(ALICE, "А сколько это длится?")
    await client.question(second, session=session, bot=make_bot(), system_prompt="SYS")

    assert llm.calls[1] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "Сколько стоит стрижка?"},
        {"role": "assistant", "content": "Мужская стрижка — 2 500 ₽."},
        {"role": "user", "content": "А сколько это длится?"},
    ]
    assert answered_text(second) == "Стрижка длится 60 минут."


async def test_answer_is_plain_text_with_booking_button(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(client, "ask_llm", FakeLLM("**Стрижка** — 2 500 ₽"))
    message = make_message(ALICE, "Цена?")

    await client.question(message, session=session, bot=make_bot(), system_prompt="SYS")

    kwargs = message.answer.call_args.kwargs
    assert kwargs["parse_mode"] is None
    button = kwargs["reply_markup"].inline_keyboard[0][0]
    assert button.text == "Записаться"
    assert button.url == "https://booking.example/test"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("[OFFTOPIC] Код не пишу, но расскажу про стрижки.", "Код не пишу, но расскажу про стрижки."),
        ("[OFFTOPIC]", client.OFF_TOPIC),
    ],
    ids=["with-text", "marker-only"],
)
async def test_off_topic_refusal_has_no_booking_button(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch, raw: str, expected: str
) -> None:
    monkeypatch.setattr(client, "ask_llm", FakeLLM(raw))
    message = make_message(ALICE, "Напиши мне код на Python")

    await client.question(message, session=session, bot=make_bot(), system_prompt="SYS")

    assert answered_text(message) == expected
    assert not has_booking_button(message)


async def test_long_message_is_cut_before_the_llm(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    llm = FakeLLM("Ок.")
    monkeypatch.setattr(client, "ask_llm", llm)

    message = make_message(ALICE, "я" * 3000)
    await client.question(message, session=session, bot=make_bot(), system_prompt="SYS")

    assert len(llm.calls[0][-1]["content"]) == MAX_MESSAGE_LENGTH


async def test_non_text_gets_only_text_reply() -> None:
    message = make_message(ALICE, None)

    await client.not_text(message)

    assert answered_text(message) == client.ONLY_TEXT
    assert not has_booking_button(message)
