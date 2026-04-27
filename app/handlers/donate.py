from __future__ import annotations

import re
from urllib.parse import urlparse

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from app.config import Config
from app.db import Database
from app.emojis import EMOJI_CHECK, EMOJI_CROSS, EMOJI_LINK
from app.keyboards import cancel_keyboard, delete_post_confirm_keyboard
from app.states import DeletePostForm
from app.texts import delete_post_admin_text, delete_post_link_prompt

router = Router(name="donate")


def _parse_post_link(raw_url: str) -> tuple[str, int] | None:
    url = raw_url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {"t.me", "telegram.me"}:
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None

    if parts[0] == "c" and len(parts) >= 3:
        internal_id = parts[1]
        message_id = parts[-1]
        if internal_id.isdigit() and message_id.isdigit():
            return f"-100{internal_id}", int(message_id)
        return None

    if parts[0] == "s" and len(parts) >= 3:
        channel = parts[1]
        message_id = parts[2]
    else:
        channel = parts[0]
        message_id = parts[1]

    if re.fullmatch(r"[A-Za-z0-9_]{5,32}", channel) and message_id.isdigit():
        return f"@{channel}", int(message_id)
    return None


async def _send_to_admins(bot, config: Config, text: str, reply_markup) -> list[Message]:
    targets = [config.admin_chat_id] if config.admin_chat_id else list(config.admin_ids)
    messages: list[Message] = []
    for chat_id in targets:
        if chat_id is None:
            continue
        messages.append(await bot.send_message(chat_id, text, reply_markup=reply_markup))
    return messages


@router.callback_query(F.data == "delete_post_pay")
async def cb_delete_post_pay(cb: CallbackQuery) -> None:
    amount = 50
    await cb.bot.send_invoice(
        chat_id=cb.message.chat.id,
        title="Удаление поста",
        description="Оплата удаления поста проверки",
        payload=f"delete_post:{cb.from_user.id}:{amount}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Удаление поста", amount=amount)],
    )
    await cb.answer()


@router.callback_query(F.data == "delete_post_check_payment")
async def cb_delete_post_check_payment(cb: CallbackQuery, state: FSMContext, db: Database) -> None:
    payment = await db.get_recent_unused_delete_payment(cb.from_user.id)
    if not payment:
        await cb.answer("Свежая оплата не найдена", show_alert=True)
        return

    await state.set_state(DeletePostForm.waiting_for_link)
    await state.update_data(delete_payment_id=payment["id"])
    await cb.message.answer(delete_post_link_prompt(), reply_markup=cancel_keyboard())
    await cb.answer()


@router.message(DeletePostForm.waiting_for_link)
async def msg_delete_post_link(
    message: Message,
    state: FSMContext,
    db: Database,
    config: Config,
) -> None:
    post_url = message.text or message.caption
    if not post_url:
        await message.answer("Отправьте ссылку на пост.", reply_markup=cancel_keyboard())
        return

    parsed = _parse_post_link(post_url)
    if not parsed:
        await message.answer(
            "Не смог разобрать ссылку. Нужен формат https://t.me/channel/123 или https://t.me/c/1234567890/123",
            reply_markup=cancel_keyboard(),
        )
        return

    data = await state.get_data()
    payment_id = data.get("delete_payment_id")
    admin_skip_payment = bool(data.get("admin_skip_payment"))
    if payment_id is None and not admin_skip_payment:
        await state.clear()
        await message.answer("Оплата не найдена. Нажмите Проверить оплату еще раз.")
        return

    target_chat_id, target_message_id = parsed
    request = await db.create_delete_post_request(
        message.from_user.id,
        int(payment_id) if payment_id is not None else None,
        post_url.strip(),
        target_chat_id,
        target_message_id,
    )
    sent = await _send_to_admins(
        message.bot,
        config,
        delete_post_admin_text(request["id"], message.from_user, post_url.strip()),
        delete_post_confirm_keyboard(request["id"]),
    )
    if sent:
        await db.set_delete_post_admin_message(request["id"], sent[0].chat.id, sent[0].message_id)

    await state.clear()
    await message.answer(f"{EMOJI_CHECK} <b>Заявка на удаление отправлена админам</b>")


@router.callback_query(F.data.startswith("delete_post_confirm:"))
async def cb_delete_post_confirm(cb: CallbackQuery, db: Database, config: Config) -> None:
    if cb.from_user.id not in config.admin_ids:
        await cb.answer()
        return

    request_id = int(cb.data.split(":", maxsplit=1)[1])
    request = await db.get_delete_post_request(request_id)
    if not request:
        await cb.answer("Уже обработано", show_alert=True)
        return

    try:
        await cb.bot.delete_message(
            chat_id=request["target_chat_id"],
            message_id=request["target_message_id"],
        )
    except Exception as exc:
        await db.finish_delete_post_request(request_id, cb.from_user.id, "failed", str(exc))
        await cb.answer("Не получилось удалить пост", show_alert=True)
        await cb.message.answer(f"{EMOJI_CROSS} <b>Ошибка удаления:</b> {str(exc)}")
        return

    request = await db.finish_delete_post_request(request_id, cb.from_user.id, "done")
    if not request:
        await cb.answer("Уже обработано", show_alert=True)
        return

    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await cb.bot.send_message(request["user_id"], f"{EMOJI_CHECK} <b>Пост удален</b>")
    await cb.answer("Удалено")


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message, db: Database, config: Config) -> None:
    payment = message.successful_payment
    await db.upsert_user(message.from_user, is_admin=message.from_user.id in config.admin_ids)
    await db.record_payment(
        user_id=message.from_user.id,
        amount=payment.total_amount,
        currency=payment.currency,
        payload=payment.invoice_payload,
        telegram_payment_charge_id=payment.telegram_payment_charge_id,
        provider_payment_charge_id=payment.provider_payment_charge_id,
    )

    if payment.invoice_payload.startswith("delete_post:"):
        await message.answer(
            f"{EMOJI_CHECK} <b>Оплата прошла</b>\n\n"
            f"{EMOJI_LINK} Нажмите Проверить оплату и отправьте ссылку на пост."
        )
        return

    await message.answer(f"{EMOJI_CHECK} <b>Оплата прошла</b>")
