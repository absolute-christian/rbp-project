from __future__ import annotations

from aiogram import Bot
from aiogram.types import FSInputFile, User

from app.config import Config
from app.keyboards import menu_keyboard
from app.texts import welcome_text


async def send_welcome(bot: Bot, chat_id: int, user: User, config: Config) -> None:
    if config.welcome_photo_path.exists():
        await bot.send_photo(
            chat_id,
            FSInputFile(config.welcome_photo_path),
            caption=welcome_text(user),
            reply_markup=menu_keyboard(),
        )
        return

    await bot.send_message(
        chat_id,
        welcome_text(user),
        reply_markup=menu_keyboard(),
    )
