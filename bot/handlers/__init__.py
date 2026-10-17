"""Handler routers, in the order the dispatcher should try them."""

from aiogram import Router


def build_router() -> Router:
    """One root router with every handler group attached."""
    router = Router(name="root")
    return router
