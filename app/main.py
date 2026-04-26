from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from app.config import load_config
from app.db import Database
from app.handlers import admin, applications, broadcast, complaints, donate, start
from app.middlewares import AppContextMiddleware


async def setup_commands(bot: Bot, admin_ids: set[int]) -> None:
    await bot.set_my_commands(
        [BotCommand(command="start", description="Открыть меню")],
        scope=BotCommandScopeDefault(),
    )
    admin_commands = [
        BotCommand(command="start", description="Открыть меню"),
        BotCommand(command="admin", description="Админ-панель"),
    ]
    for admin_id in admin_ids:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception:
            logging.warning("Cannot set admin commands for %s", admin_id, exc_info=True)


async def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    config = load_config()

    db = Database(config.db_path)
    await db.connect()
    await db.init_schema()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    middleware = AppContextMiddleware(db, config)
    dp.update.middleware(middleware)

    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(complaints.router)
    dp.include_router(applications.router)
    dp.include_router(donate.router)
    dp.include_router(broadcast.router)

    await setup_commands(bot, config.admin_ids)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
