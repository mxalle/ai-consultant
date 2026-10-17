"""Handler routers, in the order the dispatcher should try them."""

from aiogram import Router

from bot.handlers import client


def build_router() -> Router:
    """One root router with every handler group attached."""
    router = Router(name="root")
    router.include_router(client.router)
    return router
