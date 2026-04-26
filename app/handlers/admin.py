from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.config import Config
from app.db import Database
from app.keyboards import admin_panel_keyboard
from app.texts import admin_stats_text

router = Router(name="admin")


def is_admin(user_id: int, config: Config) -> bool:
    return user_id in config.admin_ids


async def send_admin_panel(message: Message, db: Database) -> None:
    stats = await db.stats()
    await message.answer(admin_stats_text(stats), reply_markup=admin_panel_keyboard())


@router.message(Command("admin"))
async def cmd_admin(message: Message, db: Database, config: Config) -> None:
    if not is_admin(message.from_user.id, config):
        return
    await db.upsert_user(message.from_user, is_admin=True)
    await send_admin_panel(message, db)


@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(cb: CallbackQuery, db: Database, config: Config) -> None:
    if not is_admin(cb.from_user.id, config):
        await cb.answer()
        return
    stats = await db.stats()
    try:
        await cb.message.edit_text(admin_stats_text(stats), reply_markup=admin_panel_keyboard())
    except Exception:
        await cb.message.answer(admin_stats_text(stats), reply_markup=admin_panel_keyboard())
    await cb.answer()


@router.callback_query(F.data == "admin_refresh")
async def cb_admin_refresh(cb: CallbackQuery, db: Database, config: Config) -> None:
    if not is_admin(cb.from_user.id, config):
        await cb.answer()
        return
    stats = await db.stats()
    await cb.message.edit_text(admin_stats_text(stats), reply_markup=admin_panel_keyboard())
    await cb.answer("Обновлено")


@router.message(F.text.regexp(r"(?i)^закрыть\s+\d+$"))
async def msg_close_ticket(message: Message, db: Database, config: Config) -> None:
    if not is_admin(message.from_user.id, config):
        return

    match = re.fullmatch(r"(?i)закрыть\s+(\d+)", message.text.strip())
    if not match:
        return

    ticket_id = int(match.group(1))
    ticket = await db.close_ticket(ticket_id, message.from_user.id)
    if not ticket:
        await message.answer(f"Тикет {ticket_id} не найден или уже закрыт")
        return

    if ticket["admin_chat_id"] and ticket["admin_message_id"]:
        try:
            await message.bot.edit_message_reply_markup(
                chat_id=ticket["admin_chat_id"],
                message_id=ticket["admin_message_id"],
                reply_markup=None,
            )
        except Exception:
            pass

    if ticket["user_status_message_id"]:
        try:
            await message.bot.delete_message(ticket["user_id"], ticket["user_status_message_id"])
        except Exception:
            pass

    await message.answer(f"Закрыт тикет {ticket_id}")
