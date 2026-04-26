from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import Config
from app.db import Database
from app.keyboards import cancel_keyboard, complaint_review_keyboard
from app.states import ComplaintForm
from app.texts import (
    active_ticket_text,
    complaint_admin_text,
    complaint_user_decision,
    ticket_sent_text,
)

router = Router(name="complaints")


async def _send_to_admins(bot: Bot, config: Config, text: str, reply_markup) -> list[Message]:
    targets = [config.admin_chat_id] if config.admin_chat_id else list(config.admin_ids)
    messages: list[Message] = []
    for chat_id in targets:
        if chat_id is None:
            continue
        messages.append(await bot.send_message(chat_id, text, reply_markup=reply_markup))
    return messages

@router.message(ComplaintForm.waiting_for_body)
async def msg_complaint_body(
    message: Message,
    bot: Bot,
    state: FSMContext,
    db: Database,
    config: Config,
) -> None:
    body = message.text or message.caption
    if not body:
        await message.answer(
            "Отправь текстом, чтобы админы могли нормально это разобрать.",
            reply_markup=cancel_keyboard(),
        )
        return

    active = await db.has_active_ticket(message.from_user.id)
    if active:
        await state.clear()
        await message.answer(active_ticket_text(active["type"]))
        return

    await db.upsert_user(message.from_user, is_admin=message.from_user.id in config.admin_ids)
    ticket = await db.create_ticket(message.from_user.id, "complaint", body, "жалоба")
    sent = await _send_to_admins(
        bot,
        config,
        complaint_admin_text(ticket["id"], message.from_user, body, "жалоба"),
        complaint_review_keyboard(ticket["id"]),
    )
    if sent:
        await db.set_ticket_admin_message(ticket["id"], sent[0].chat.id, sent[0].message_id)

    await state.clear()
    status_msg = await message.answer(ticket_sent_text("complaint"))
    await db.set_ticket_user_status_message(ticket["id"], status_msg.message_id)


@router.callback_query(F.data.startswith("complaint_decide:"))
async def cb_complaint_decide(cb: CallbackQuery, bot: Bot, db: Database, config: Config) -> None:
    if cb.from_user.id not in config.admin_ids:
        await cb.answer()
        return

    _, ticket_id_raw, decision = cb.data.split(":", maxsplit=2)
    ticket_id = int(ticket_id_raw)
    status = "approved" if decision == "approve" else "rejected"
    ticket = await db.finish_pending_ticket(ticket_id, status, cb.from_user.id)
    if not ticket:
        await cb.answer("Уже обработано", show_alert=True)
        return

    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if ticket["user_status_message_id"]:
        try:
            await bot.delete_message(ticket["user_id"], ticket["user_status_message_id"])
        except Exception:
            pass

    await bot.send_message(ticket["user_id"], complaint_user_decision(status))
    await cb.answer("Готово")
