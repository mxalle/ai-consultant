"""Handler routers, in the order the dispatcher should try them."""

from aiogram import Router

from bot.handlers import client, owner


def build_router() -> Router:
    """One root router with every handler group attached.

    The owner router goes first: the owner chat is a private chat too, and it
    must never reach the client handlers (and the LLM).
    """
    router = Router(name="root")
    router.include_router(owner.router)
    router.include_router(client.router)
    return router
