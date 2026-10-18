"""OpenAI-compatible chat client: OpenRouter, YandexGPT, anything with /chat/completions.

Which provider is used is decided by LLM_BASE_URL / LLM_API_KEY / LLM_MODEL only.
"""

from openai import AsyncOpenAI, OpenAIError

from app.config import settings

_client: AsyncOpenAI | None = None


class LLMError(Exception):
    """The model did not give a usable answer: API error, timeout or empty reply."""


def get_client() -> AsyncOpenAI:
    """One client per process, created on first use from the current settings."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout,
            max_retries=1,
        )
    return _client


async def ask_llm(messages: list[dict[str, str]]) -> str:
    """Send the chat (system prompt first) and return the answer text."""
    extra_body = {"reasoning": {"enabled": False}} if settings.llm_disable_reasoning else None
    try:
        response = await get_client().chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=0.3,
            max_tokens=400,
            extra_body=extra_body,
        )
    except OpenAIError as exc:
        raise LLMError(f"{type(exc).__name__}: {exc}") from exc

    content = response.choices[0].message.content if response.choices else None
    if not content or not content.strip():
        raise LLMError("empty completion")
    return content.strip()
