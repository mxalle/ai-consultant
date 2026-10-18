# ai-consultant

Telegram bot that answers a local business's clients (barbershop, tattoo studio,
detailing) from a plain-text knowledge base through an LLM, puts a «Записаться»
booking button under its answers, and hands anything that needs a human decision
to the owner, whose reply is relayed back to the client. MVP for demos: one business
per bot process.

## Stack

- aiogram 3 (long polling), SQLAlchemy 2.0 (async), asyncpg, Alembic, pydantic-settings
- `openai` package (`AsyncOpenAI`) against any OpenAI-compatible endpoint
- PostgreSQL 16 via `docker-compose.yml` (host port 5433)
- pytest + pytest-asyncio; tests run on SQLite (aiosqlite), no Docker, no network

## Layout

```
app/config.py              Settings (pydantic-settings, .env)
app/database.py            async engine, session_factory, Base
app/models.py              Conversation, ChatMessage, Escalation
app/services/conversations.py  save message, history (last 10), /reset
app/services/escalations.py    create / find by owner message / mark answered
app/services/rate_limit.py     user messages within the last hour
app/services/stats.py          numbers for /stats
bot/main.py                entrypoint: settings check, knowledge -> prompt, polling
bot/middlewares.py         one DB session per update
bot/prompt.py              system prompt, reply markers, truncation
bot/llm.py                 ask_llm(), LLMError
bot/keyboards.py           booking button
bot/handlers/owner.py      owner chat: replies to escalations, /start, /stats
bot/handlers/client.py     client chat: /start, /reset, questions, non-text
knowledge/                 one <slug>.md per business
alembic/                   migrations
tests/                     pytest suite; tests/fakes.py stands in for aiogram objects
```

## Rules

1. **Answers come only from the knowledge base.** `KNOWLEDGE_FILE` is read once at
   startup and put whole into the system prompt (`bot/prompt.py`). No RAG, no
   embeddings. Changing the file needs a restart.
2. **Reply markers.** `[ESCALATE]` only when a human must decide: reschedule or
   cancel, complaint, a discount or special request, refund, «позовите
   администратора». A fact missing from the knowledge base gets an honest
   «Этого, к сожалению, не подскажу», not an escalation — otherwise the owner is
   flooded and switches the bot off. `[OFFTOPIC]` marks a refusal of an off-topic
   request. `parse_reply` reads either marker anywhere and strips it — none may
   reach a client; `[ESCALATE]` wins over `[OFFTOPIC]`. On escalation the client
   gets `ESCALATED`, the owner gets the question; the bot's message id in the
   owner chat is stored in `escalations.owner_message_id`, and the owner's reply
   to that message is how the client is found again.
3. **Booking button** only under `/start` and ordinary model answers about the
   business. System messages (`FALLBACK`, `ESCALATED`, `RATE_LIMITED`,
   `ONLY_TEXT`, `RESET_DONE`), off-topic refusals and relayed owner answers
   carry none, so their texts must not say «по кнопке».
4. **The owner never goes through the LLM.** The owner router is included before
   the client router; everything from `OWNER_CHAT_ID` stops there.
5. **Plain text everywhere.** No default `parse_mode`: bot output is either model
   output or client text, and stray markdown/HTML must not break a send.
6. **Failures are polite.** Any `LLMError` (API error, timeout, empty reply) ->
   the client gets `FALLBACK`, the error goes to the log.
   An unreachable owner chat also means `FALLBACK`, never a promise to answer.
7. **History.** The last `HISTORY_LIMIT = 10` non-archived messages of this client
   go to the LLM. `/reset` only sets `messages.archived`; rows stay so `/reset`
   cannot lift the rate limit and `/stats` stays honest.
8. **Rate limit** = `RATE_LIMIT_PER_HOUR` user messages per rolling hour, counted
   from `messages`. A refused message is not stored and makes no LLM call.
   Client text over 1000 characters is cut before it is stored and sent.
9. **Handlers stay thin.** Every DB query lives in `app/services/*`. Handlers are
   plain async functions; tests call them directly with `tests/fakes.py` objects
   and a monkeypatched `ask_llm` / `llm.get_client`.
10. Tests must cover prompt assembly, the markers, history limit and isolation,
   the rate limit, owner replies and the LLM fallback, and must all pass.
   No real LLM or Telegram calls in tests.
11. Keep it small. No FastAPI, Mini App, Redis, multi-tenancy or admin panel —
    those are next steps if the demo lands. No abstractions "for later".

## Commands

```bash
.venv/bin/python -m bot.main              # run the bot (needs a filled .env)
.venv/bin/pytest                          # run tests (SQLite)
.venv/bin/alembic upgrade head            # apply migrations (needs Postgres)
docker compose up -d                      # postgres on localhost:5433
```

See `README.md` for setting up a new business.
