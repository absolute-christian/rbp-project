from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import Config
from app.db import Database
from app.keyboards import application_review_keyboard, cancel_keyboard
from app.states import ApplicationDecisionForm, ApplicationForm
from app.texts import (
    active_ticket_text,
    application_admin_text,
    application_user_decision,
    ticket_sent_text,
)

router = Router(name="applications")


async def _send_to_admins(bot: Bot, config: Config, text: str, reply_markup) -> list[Message]:
    targets = [config.admin_chat_id] if config.admin_chat_id else list(config.admin_ids)
    messages: list[Message] = []
    for chat_id in targets:
        if chat_id is None:
            continue
        messages.append(await bot.send_message(chat_id, text, reply_markup=reply_markup))
    return messages


@router.message(ApplicationForm.waiting_for_body)
async def msg_application_body(
    message: Message,
    bot: Bot,
    state: FSMContext,
    db: Database,
    config: Config,
) -> None:
    body = message.text or message.caption
    if not body:
        await message.answer(
            "Заполни анкету",
            reply_markup=cancel_keyboard(),
        )
        return

    active = await db.has_active_ticket(message.from_user.id)
    if active:
        await state.clear()
        await message.answer(active_ticket_text(active["type"]))
        return

    data = await state.get_data()
    application_kind = data.get("application_kind")

    await db.upsert_user(message.from_user, is_admin=message.from_user.id in config.admin_ids)
    ticket = await db.create_ticket(message.from_user.id, "application", body, application_kind)
    sent = await _send_to_admins(
        bot,
        config,
        application_admin_text(ticket["id"], message.from_user, body, application_kind),
        application_review_keyboard(ticket["id"]),
    )
    if sent:
        await db.set_ticket_admin_message(ticket["id"], sent[0].chat.id, sent[0].message_id)

    await state.clear()
    status_msg = await message.answer(ticket_sent_text("application"))
    await db.set_ticket_user_status_message(ticket["id"], status_msg.message_id)


@router.callback_query(F.data.startswith("application_decide:"))
async def cb_application_decide(
    cb: CallbackQuery,
    state: FSMContext,
    db: Database,
    config: Config,
) -> None:
    if cb.from_user.id not in config.admin_ids:
        await cb.answer()
        return

    _, ticket_id_raw, decision = cb.data.split(":", maxsplit=2)
    ticket_id = int(ticket_id_raw)
    ticket = await db.lock_application_for_review(ticket_id, cb.from_user.id)
    if not ticket:
        await cb.answer("Уже обрабатывается или закрыто", show_alert=True)
        return

    status = "approved" if decision == "approve" else "rejected"
    await state.set_state(ApplicationDecisionForm.waiting_for_note)
    await state.update_data(
        ticket_id=ticket_id,
        status=status,
        admin_chat_id=cb.message.chat.id,
        admin_message_id=cb.message.message_id,
    )
    await cb.message.reply(
        "Напиши причиной/примечанием в ответ на это сообщение, чтобы отправить пользователю полный ответ по заявке"
    )
    await cb.answer()


@router.message(ApplicationDecisionForm.waiting_for_note)
async def msg_application_note(message: Message, bot: Bot, state: FSMContext, db: Database, config: Config) -> None:
    if message.from_user.id not in config.admin_ids:
        return
    note = message.text or message.caption
    if not note:
        await message.answer("Нужен текст причины или примечания.")
        return

    data = await state.get_data()
    ticket_id = int(data["ticket_id"])
    status = data["status"]
    ticket = await db.finish_reviewing_application(ticket_id, message.from_user.id, status, note)
    if not ticket:
        await state.clear()
        await message.answer("Эта заявка уже не ждет твоего решения")
        return

    try:
        await bot.edit_message_reply_markup(
            chat_id=data.get("admin_chat_id"),
            message_id=data.get("admin_message_id"),
            reply_markup=None,
        )
    except Exception:
        pass

    if ticket["user_status_message_id"]:
        try:
            await bot.delete_message(ticket["user_id"], ticket["user_status_message_id"])
        except Exception:
            pass

    await bot.send_message(ticket["user_id"], application_user_decision(status, note))
    await state.clear()
    await message.answer("Ответ отправлен пользователю")
