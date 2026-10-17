from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import settings

BOOKING_BUTTON = "Записаться"


def booking_keyboard() -> InlineKeyboardMarkup:
    """The «Записаться» button that goes under every answer to a client."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=BOOKING_BUTTON, url=settings.booking_url)]]
    )
