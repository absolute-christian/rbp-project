from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import Config
from app.db import Database
from app.keyboards import (
    MENU_ADMIN,
    MENU_COMPLAINT,
    MENU_CONTACT,
    MENU_DELETE_POST,
    MENU_UNION,
    cancel_keyboard,
    delete_post_keyboard,
)
from app.states import ApplicationForm, ComplaintForm
from app.states import DeletePostForm
from app.texts import active_ticket_text, application_prompt, complaint_prompt, delete_post_link_prompt, delete_post_text
from app.ui import send_welcome

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, state: FSMContext, db: Database, config: Config) -> None:
    await state.clear()
    await db.upsert_user(message.from_user, is_admin=message.from_user.id in config.admin_ids)
    await send_welcome(bot, message.chat.id, message.from_user, config)


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(cb: CallbackQuery, bot: Bot, state: FSMContext, db: Database, config: Config) -> None:
    await state.clear()
    await db.upsert_user(cb.from_user, is_admin=cb.from_user.id in config.admin_ids)
    try:
        await cb.message.delete()
    except Exception:
        pass
    await send_welcome(bot, cb.message.chat.id, cb.from_user, config)
    await cb.answer()


@router.message(F.text == MENU_DELETE_POST)
async def msg_delete_post(message: Message, state: FSMContext, db: Database, config: Config) -> None:
    await state.clear()
    await db.upsert_user(message.from_user, is_admin=message.from_user.id in config.admin_ids)
    if message.from_user.id in config.admin_ids:
        await state.set_state(DeletePostForm.waiting_for_link)
        await state.update_data(delete_payment_id=None, admin_skip_payment=True)
        await message.answer(delete_post_link_prompt(), reply_markup=cancel_keyboard())
        return

    await message.answer(delete_post_text(), reply_markup=delete_post_keyboard())


@router.message(F.text == MENU_COMPLAINT)
async def msg_menu_complaint(message: Message, state: FSMContext, db: Database, config: Config) -> None:
    await db.upsert_user(message.from_user, is_admin=message.from_user.id in config.admin_ids)
    active = await db.has_active_ticket(message.from_user.id)
    if active:
        await state.clear()
        await message.answer(active_ticket_text(active["type"]))
        return

    await state.set_state(ComplaintForm.waiting_for_body)
    await message.answer(complaint_prompt(), reply_markup=cancel_keyboard())


@router.message(F.text.in_({MENU_UNION, MENU_ADMIN, MENU_CONTACT}))
async def msg_menu_application(message: Message, state: FSMContext, db: Database, config: Config) -> None:
    await db.upsert_user(message.from_user, is_admin=message.from_user.id in config.admin_ids)
    active = await db.has_active_ticket(message.from_user.id)
    if active:
        await state.clear()
        await message.answer(active_ticket_text(active["type"]))
        return

    prompts = {
        MENU_UNION: (
            "Предложить союз",
            "заявка союза",
            "Напишите кто вы такие, какой проект представляете и какие выгоды видите в сюзе с нами",
        ),
        MENU_ADMIN: (
            "Стать админом",
            "заявка адм",
            "Опишите ваш опыт, скажите ваш часовой пояс, возраст, имя и чем можете быть полезны в разъебах",
        ),
        MENU_CONTACT: (
            "Связь с админами",
            "вопрос",
            "Опишите вопрос одним сообщением. Админы ответят через некоторое время",
        ),
    }
    title, kind_label, prompt = prompts[message.text]
    await state.set_state(ApplicationForm.waiting_for_body)
    await state.update_data(application_kind=kind_label)
    await message.answer(application_prompt(title, prompt), reply_markup=cancel_keyboard())
