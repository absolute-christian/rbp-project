from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from aiogram import Bot, F, Router
from aiogram.enums import MessageEntityType
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.config import Config
from app.db import Database
from app.emojis import (
    EMOJI_CHECK,
    EMOJI_CROSS,
    EMOJI_INFO,
    EMOJI_LINK,
    EMOJI_LOADING,
    EMOJI_MEDIA,
    EMOJI_TEXT_ADD,
)
from app.keyboards import btn, broadcast_back_keyboard
from app.states import BroadcastForm

router = Router(name="broadcast")


def _bc_build_reply_markup(
    btn_text: str | None,
    btn_url: str | None,
    btn_emoji_id: str | None,
) -> InlineKeyboardMarkup | None:
    if not btn_text and not btn_emoji_id:
        return None
    if not btn_url:
        return None
    text = btn_text or "·"
    button = btn(text, url=btn_url)
    if btn_emoji_id:
        button.icon_custom_emoji_id = btn_emoji_id
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


def _valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(cb: CallbackQuery, state: FSMContext, config: Config) -> None:
    if cb.from_user.id not in config.admin_ids:
        await cb.answer()
        return
    await state.set_state(BroadcastForm.waiting_for_text)
    msg = await cb.message.edit_text(
        f"<b>Шаг 1: отправь текст сообщения для рассылки</b>",
        reply_markup=broadcast_back_keyboard(),
    )
    await state.update_data(step1_msg_id=msg.message_id)
    await cb.answer()


@router.message(BroadcastForm.waiting_for_text)
async def bc_receive_text(msg: Message, state: FSMContext, config: Config) -> None:
    if msg.from_user.id not in config.admin_ids:
        return
    body = msg.text or msg.caption
    if not body:
        await msg.answer(
            f"{EMOJI_CROSS} <b>отправь текст или подпись к медиа</b>",
            reply_markup=broadcast_back_keyboard(),
        )
        return

    data = await state.get_data()
    try:
        await msg.bot.delete_message(msg.chat.id, data.get("step1_msg_id"))
    except Exception:
        pass
    try:
        await msg.delete()
    except Exception:
        pass

    await state.update_data(
        bc_text=body,
        bc_entities=msg.entities or msg.caption_entities,
    )
    await state.set_state(BroadcastForm.waiting_for_media)

    step_msg = await msg.bot.send_message(
        msg.chat.id,
        f"{EMOJI_MEDIA} <b>Шаг 2: отправь медиа (фото, видео, GIF) или нажми Пропустить</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [btn("Пропустить", callback_data="bc_skip_media", emoji="down")],
                [btn("Отмена", callback_data="admin_panel")],
            ]
        ),
    )
    await state.update_data(step2_msg_id=step_msg.message_id)


@router.message(BroadcastForm.waiting_for_media, F.photo | F.video | F.animation)
async def bc_receive_media(msg: Message, state: FSMContext, config: Config) -> None:
    if msg.from_user.id not in config.admin_ids:
        return
    data = await state.get_data()
    try:
        await msg.bot.delete_message(msg.chat.id, data.get("step2_msg_id"))
    except Exception:
        pass
    try:
        await msg.delete()
    except Exception:
        pass

    if msg.photo:
        await state.update_data(bc_photo=msg.photo[-1].file_id, bc_video=None, bc_animation=None)
    elif msg.video:
        await state.update_data(bc_photo=None, bc_video=msg.video.file_id, bc_animation=None)
    elif msg.animation:
        await state.update_data(bc_photo=None, bc_video=None, bc_animation=msg.animation.file_id)

    await _bc_ask_button(msg.bot, msg.chat.id, state)


@router.callback_query(F.data == "bc_skip_media", BroadcastForm.waiting_for_media)
async def bc_skip_media(cb: CallbackQuery, state: FSMContext, config: Config) -> None:
    if cb.from_user.id not in config.admin_ids:
        await cb.answer()
        return
    data = await state.get_data()
    try:
        await cb.bot.delete_message(cb.message.chat.id, data.get("step2_msg_id"))
    except Exception:
        pass
    await state.update_data(bc_photo=None, bc_video=None, bc_animation=None)
    await _bc_ask_button(cb.bot, cb.message.chat.id, state)
    await cb.answer()


async def _bc_ask_button(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(BroadcastForm.waiting_for_btn_text)
    step_msg = await bot.send_message(
        chat_id,
        f"{EMOJI_LINK} <b>Шаг 3: добавить кнопку со ссылкой?</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [btn("Добавить кнопку", callback_data="bc_add_button", emoji="link")],
                [btn("Без кнопки", callback_data="bc_skip_button", emoji="down")],
                [btn("Отмена", callback_data="admin_panel")],
            ]
        ),
    )
    await state.update_data(step3_msg_id=step_msg.message_id)


@router.callback_query(F.data == "bc_add_button", BroadcastForm.waiting_for_btn_text)
async def bc_add_button(cb: CallbackQuery, state: FSMContext, config: Config) -> None:
    if cb.from_user.id not in config.admin_ids:
        await cb.answer()
        return
    data = await state.get_data()
    try:
        await cb.bot.delete_message(cb.message.chat.id, data.get("step3_msg_id"))
    except Exception:
        pass
    step_msg = await cb.bot.send_message(
        cb.message.chat.id,
        f"{EMOJI_TEXT_ADD} <b>Шаг 4: введи текст кнопки</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("◁ Отмена", callback_data="admin_panel")]]),
    )
    await state.update_data(step4_msg_id=step_msg.message_id)
    await cb.answer()


@router.message(BroadcastForm.waiting_for_btn_text)
async def bc_receive_btn_text(msg: Message, state: FSMContext, config: Config) -> None:
    if msg.from_user.id not in config.admin_ids:
        return
    data = await state.get_data()

    btn_text = msg.text or ""
    btn_emoji_id = None
    if msg.entities:
        for entity in msg.entities:
            if entity.type == MessageEntityType.CUSTOM_EMOJI:
                btn_emoji_id = entity.custom_emoji_id
                btn_text = (btn_text[: entity.offset] + btn_text[entity.offset + entity.length :]).strip()
                break

    if not btn_text and not btn_emoji_id:
        err = await msg.answer(
            f"{EMOJI_CROSS} <b>Текст кнопки не может быть пустым</b>"
        )
        await state.update_data(step4_err_id=err.message_id)
        return

    prev_err = data.get("step4_err_id")
    if prev_err:
        try:
            await msg.bot.delete_message(msg.chat.id, prev_err)
        except Exception:
            pass

    await state.update_data(bc_btn_text=btn_text, bc_btn_emoji_id=btn_emoji_id)
    try:
        await msg.bot.delete_message(msg.chat.id, data.get("step4_msg_id"))
    except Exception:
        pass
    try:
        await msg.delete()
    except Exception:
        pass

    await state.set_state(BroadcastForm.waiting_for_btn_url)
    step_msg = await msg.bot.send_message(
        msg.chat.id,
        f"{EMOJI_LINK} <b>Шаг 5: введи ссылку (URL) для кнопки</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("Отмена", callback_data="admin_panel")]]),
    )
    await state.update_data(step5_msg_id=step_msg.message_id)


@router.message(BroadcastForm.waiting_for_btn_url)
async def bc_receive_btn_url(msg: Message, state: FSMContext, config: Config) -> None:
    if msg.from_user.id not in config.admin_ids:
        return
    url = (msg.text or "").strip()
    if not _valid_url(url):
        await msg.answer(
            f"{EMOJI_CROSS} <b>Нужна ссылка формата https://example.com</b>"
        )
        return

    data = await state.get_data()
    try:
        await msg.bot.delete_message(msg.chat.id, data.get("step5_msg_id"))
    except Exception:
        pass
    try:
        await msg.delete()
    except Exception:
        pass
    await state.update_data(bc_btn_url=url)
    await _bc_show_preview(msg.bot, msg.chat.id, state)


@router.callback_query(F.data == "bc_skip_button", BroadcastForm.waiting_for_btn_text)
async def bc_skip_button(cb: CallbackQuery, state: FSMContext, config: Config) -> None:
    if cb.from_user.id not in config.admin_ids:
        await cb.answer()
        return
    data = await state.get_data()
    try:
        await cb.bot.delete_message(cb.message.chat.id, data.get("step3_msg_id"))
    except Exception:
        pass
    await state.update_data(bc_btn_text=None, bc_btn_url=None, bc_btn_emoji_id=None)
    await _bc_show_preview(cb.bot, cb.message.chat.id, state)
    await cb.answer()


async def _bc_show_preview(bot: Bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    bc_text = data.get("bc_text")
    bc_entities = data.get("bc_entities")
    bc_photo = data.get("bc_photo")
    bc_video = data.get("bc_video")
    bc_animation = data.get("bc_animation")
    reply_markup = _bc_build_reply_markup(
        data.get("bc_btn_text"),
        data.get("bc_btn_url"),
        data.get("bc_btn_emoji_id"),
    )

    head = await bot.send_message(
        chat_id,
        f"<b>Предпросмотр рассылки:</b>",
    )

    if bc_photo:
        preview = await bot.send_photo(chat_id, bc_photo, caption=bc_text, caption_entities=bc_entities, reply_markup=reply_markup, parse_mode=None)
    elif bc_video:
        preview = await bot.send_video(chat_id, bc_video, caption=bc_text, caption_entities=bc_entities, reply_markup=reply_markup, parse_mode=None)
    elif bc_animation:
        preview = await bot.send_animation(chat_id, bc_animation, caption=bc_text, caption_entities=bc_entities, reply_markup=reply_markup, parse_mode=None)
    else:
        preview = await bot.send_message(chat_id, bc_text, entities=bc_entities, reply_markup=reply_markup, parse_mode=None)

    confirm_msg = await bot.send_message(
        chat_id,
        f"{EMOJI_INFO} <b>Отправить рассылку?</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    btn("Отправить", callback_data="bc_confirm", emoji="send"),
                    btn("Отмена", callback_data="bc_cancel_preview", emoji="cross"),
                ]
            ]
        ),
    )
    await state.update_data(
        preview_head_id=head.message_id,
        preview_msg_id=preview.message_id,
        confirm_msg_id=confirm_msg.message_id,
    )


@router.callback_query(F.data == "bc_confirm")
async def bc_confirm(cb: CallbackQuery, state: FSMContext, db: Database, config: Config) -> None:
    if cb.from_user.id not in config.admin_ids:
        await cb.answer()
        return
    data = await state.get_data()

    for mid in [data.get("confirm_msg_id"), data.get("preview_msg_id"), data.get("preview_head_id")]:
        if mid:
            try:
                await cb.bot.delete_message(cb.message.chat.id, mid)
            except Exception:
                pass

    reply_markup = _bc_build_reply_markup(
        data.get("bc_btn_text"),
        data.get("bc_btn_url"),
        data.get("bc_btn_emoji_id"),
    )
    users = await db.get_all_broadcast_users()
    success = failed = 0

    status_msg = await cb.bot.send_message(
        cb.message.chat.id,
        f"{EMOJI_LOADING} <b>Рассылка начата...</b>",
    )

    for uid in users:
        try:
            if data.get("bc_photo"):
                await cb.bot.send_photo(uid, data["bc_photo"], caption=data.get("bc_text"), caption_entities=data.get("bc_entities"), reply_markup=reply_markup, parse_mode=None)
            elif data.get("bc_video"):
                await cb.bot.send_video(uid, data["bc_video"], caption=data.get("bc_text"), caption_entities=data.get("bc_entities"), reply_markup=reply_markup, parse_mode=None)
            elif data.get("bc_animation"):
                await cb.bot.send_animation(uid, data["bc_animation"], caption=data.get("bc_text"), caption_entities=data.get("bc_entities"), reply_markup=reply_markup, parse_mode=None)
            else:
                await cb.bot.send_message(uid, data.get("bc_text"), entities=data.get("bc_entities"), reply_markup=reply_markup, parse_mode=None)
            success += 1
        except TelegramForbiddenError:
            failed += 1
            await db.mark_user_blocked(uid)
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await state.clear()
    await status_msg.edit_text(
        f"{EMOJI_CHECK} <b>Рассылка завершена</b>\n\n"
        f"{EMOJI_CHECK} <b>Успешно:</b> <b>{success}</b>\n"
        f"{EMOJI_CROSS} <b>Ошибок:</b> <b>{failed}</b>",
        reply_markup=broadcast_back_keyboard(),
    )
    await cb.answer()


@router.callback_query(F.data == "bc_cancel_preview")
async def bc_cancel_preview(cb: CallbackQuery, state: FSMContext, config: Config) -> None:
    if cb.from_user.id not in config.admin_ids:
        await cb.answer()
        return
    data = await state.get_data()
    for mid in [data.get("confirm_msg_id"), data.get("preview_msg_id"), data.get("preview_head_id")]:
        if mid:
            try:
                await cb.bot.delete_message(cb.message.chat.id, mid)
            except Exception:
                pass
    await state.clear()
    await cb.message.answer(
        f"{EMOJI_CROSS} <b>Рассылка отменена</b>",
        reply_markup=broadcast_back_keyboard(),
    )
    await cb.answer()
