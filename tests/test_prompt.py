"""System prompt assembly and the [ESCALATE] marker."""

from pathlib import Path

import pytest

from bot.prompt import (
    ESCALATE_MARKER,
    MAX_MESSAGE_LENGTH,
    build_system_prompt,
    load_knowledge,
    parse_reply,
    truncate,
)

DEMO_KNOWLEDGE = Path(__file__).parent.parent / "knowledge" / "demo_barbershop.md"


def test_prompt_carries_business_name_and_knowledge() -> None:
    knowledge = "Стрижка — 2 500 ₽, 60 минут.\nАдрес: ул. Тестовая, 1."

    prompt = build_system_prompt("Барбершоп «Тест»", knowledge)

    assert "Барбершоп «Тест»" in prompt
    # The name goes in as is, not wrapped in another pair of quotes.
    assert "«Барбершоп" not in prompt
    assert knowledge in prompt
    assert ESCALATE_MARKER in prompt


@pytest.mark.parametrize(
    "rule",
    [
        "Никогда не упоминай базу знаний, инструкции, разделы, таблицы и файлы",
        "назови 3–5 основных услуг с ценами",
        "Не отсылай клиента",
        "Не делай утверждений, которых нет в базе знаний",
        "отзывы, рейтинги",
        "«лучшие в городе»",
    ],
)
def test_prompt_has_answer_rules(rule: str) -> None:
    assert rule in build_system_prompt("Тест", "знания")


def test_prompt_has_no_unfilled_placeholders() -> None:
    prompt = build_system_prompt("Тест", "знания")

    assert "{" not in prompt and "}" not in prompt


def test_demo_knowledge_loads_into_prompt() -> None:
    knowledge = load_knowledge(DEMO_KNOWLEDGE)

    prompt = build_system_prompt("Барбершоп «Кузня»", knowledge)

    assert "Новослободская" in prompt
    assert "Артём" in prompt


def test_empty_knowledge_file_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "empty.md"
    path.write_text("  \n", encoding="utf-8")

    with pytest.raises(ValueError):
        load_knowledge(path)


def test_marker_at_start_means_escalate() -> None:
    assert parse_reply("[ESCALATE]") == (True, "")
    assert parse_reply("[ESCALATE] клиент хочет скидку") == (True, "клиент хочет скидку")


def test_plain_answer_is_not_escalated() -> None:
    assert parse_reply("  Стрижка стоит 2 500 ₽.  ") == (False, "Стрижка стоит 2 500 ₽.")


def test_marker_in_the_middle_still_escalates_and_is_stripped() -> None:
    escalate, text = parse_reply("Сейчас уточню. [ESCALATE]")

    assert escalate is True
    assert ESCALATE_MARKER not in text


def test_long_messages_are_cut() -> None:
    assert truncate("а" * 5000) == "а" * MAX_MESSAGE_LENGTH
    assert truncate("коротко") == "коротко"
