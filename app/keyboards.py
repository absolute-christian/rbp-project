from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.emojis import CUSTOM_EMOJI_IDS


MENU_DELETE_POST = "Удалить пост"
MENU_UNION = "Союз"
MENU_ADMIN = "Стать админом"
MENU_CONTACT = "Связь"
MENU_COMPLAINT = "Пожаловаться"


def btn(
    text: str,
    *,
    callback_data: str | None = None,
    url: str | None = None,
    emoji: str | None = None,
) -> InlineKeyboardButton:
    kwargs = {}
    if emoji:
        kwargs["icon_custom_emoji_id"] = CUSTOM_EMOJI_IDS[emoji]
    return InlineKeyboardButton(text=text, callback_data=callback_data, url=url, **kwargs)


def menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [kb(MENU_DELETE_POST, "trash")],
            [kb(MENU_UNION, "link"), kb(MENU_ADMIN, "person_ok")],
            [kb(MENU_CONTACT, "paperclip"), kb(MENU_COMPLAINT, "megaphone")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def kb(text: str, emoji: str) -> KeyboardButton:
    return KeyboardButton(text=text, icon_custom_emoji_id=CUSTOM_EMOJI_IDS[emoji])


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[btn("Отмена", callback_data="main_menu")]]
    )


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("Рассылка", callback_data="admin_broadcast", emoji="megaphone")],
            [btn("Обновить статистику", callback_data="admin_refresh", emoji="stats")],
        ]
    )


def complaint_review_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                btn("Проверим", callback_data=f"complaint_decide:{ticket_id}:approve", emoji="check"),
                btn("Нахуй", callback_data=f"complaint_decide:{ticket_id}:reject", emoji="cross"),
            ]
        ]
    )


def application_review_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                btn("Одобрить", callback_data=f"application_decide:{ticket_id}:approve", emoji="check"),
                btn("Отказать", callback_data=f"application_decide:{ticket_id}:reject", emoji="cross"),
            ]
        ]
    )


def delete_post_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("Оплатить 50 звезд", callback_data="delete_post_pay", emoji="send_money")],
            [btn("Проверить оплату", callback_data="delete_post_check_payment", emoji="check")],
            [btn("Назад", callback_data="main_menu")],
        ]
    )


def delete_post_confirm_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("Подтвердить удаление", callback_data=f"delete_post_confirm:{request_id}", emoji="check")],
        ]
    )


def broadcast_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[btn("Назад", callback_data="admin_panel")]]
    )
