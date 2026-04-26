from __future__ import annotations

from html import escape

from aiogram.types import User

from app.emojis import (
    EMOJI_BOT,
    EMOJI_CHECK,
    EMOJI_CLOCK,
    EMOJI_CROSS,
    EMOJI_FILE,
    EMOJI_HEART,
    EMOJI_MEGAPHONE,
    EMOJI_PEOPLE,
    EMOJI_PERSON_NO,
    EMOJI_PERSON_OK,
    EMOJI_SMILE,
    EMOJI_STATS,
    EMOJI_TAG,
    EMOJI_TRASH,
    EMOJI_WRITE,
)


PROJECT_NAME = "РБП - Разъеб ботов поддержки"


def user_label(user: User) -> str:
    name = escape(user.full_name or "Без имени")
    username = f"@{escape(user.username)}" if user.username else "без username"
    return f"{name} ({username} / <code>{user.id}</code>)"


def admin_user_label(row) -> str:
    name = escape(row["first_name"] or "Без имени")
    username = f"@{escape(row['username'])}" if row["username"] else "без username"
    return f"{name} ({username} / <code>{row['user_id']}</code>)"


def welcome_text(user: User) -> str:
    return (
        f"<b>{EMOJI_BOT} {PROJECT_NAME}</b>\n\n"
        f"{EMOJI_SMILE} Привет <b>{escape(user.first_name or 'друн')}</b>\n"
        "Открой меню и выбери что нужно"
    )


def complaint_prompt() -> str:
    return (
        f"{EMOJI_MEGAPHONE} <b>Пожаловаться</b>\n\n"
        "Опиши жалобу одним сообщением проблему, дай нам ссылку или юз бота, кого надо разъебать"
    )


def application_prompt(title: str = "Анкеточка", body: str | None = None) -> str:
    prompt = body or "Отправь заявку одним сообщением. Чем конкретнее, тем быстрее разберем."
    return (
        f"{EMOJI_WRITE} <b>{escape(title)}</b>\n\n"
        f"{escape(prompt)}"
    )


def delete_post_text() -> str:
    return (
        f"<b>{EMOJI_TRASH} Удалить пост проверки</b>\n\n"
        "Оплата через звезды. После платежа напишите админам детали поста через кнопку связи и прикрепите скрин с оплатой"
    )


def active_ticket_text(ticket_type: str) -> str:
    name = "жалоба" if ticket_type == "complaint" else "заявочка"
    return (
        f"{EMOJI_CLOCK} <b>У тебя уже есть активная {name}</b>\n\n"
        "Жди пока админы рассмотрят ее, не нужно создавать новую"
    )


def complaint_admin_text(
    ticket_id: int,
    user: User,
    body: str,
    kind_label: str = "жалоба",
) -> str:
    return (
        f"<b>{EMOJI_FILE} Жалоба {ticket_id} от {user_label(user)}</b>\n"
        f"{EMOJI_TAG} <b>{escape(kind_label)}</b>\n\n"
        f"{escape(body)}"
    )


def application_admin_text(
    ticket_id: int,
    user: User,
    body: str,
    kind_label: str | None = None,
) -> str:
    kind = f"\n{EMOJI_TAG} <b>{escape(kind_label)}</b>" if kind_label else ""
    return (
        f"<b>{EMOJI_FILE} Заявочка {ticket_id} от {user_label(user)}</b>"
        f"{kind}\n\n"
        f"<blockquote>{escape(body)}</blockquote>"
    )


def ticket_sent_text(kind: str) -> str:
    label = "Жалоба" if kind == "complaint" else "Заявочка"
    return (
        f"{EMOJI_CHECK} <b>{label} отправлена на рассмотрение</b>\n\n"
        "Жди вердикта админов, мы не заставим долго ждать"
    )


def complaint_user_decision(status: str) -> str:
    if status == "approved":
        return (
            f"{EMOJI_PERSON_OK} <b>Админы начнут работать по твоей инфе</b>\n\n"
            f"{EMOJI_HEART} Спасибо за инфу"
        )
    return (
        f"{EMOJI_PERSON_NO} <b>Жалобу отклонили</b>\n\n"
        "По инфе не будут работать либо уже есть пост о боте"
    )


def application_user_decision(status: str, note: str) -> str:
    title = "Твоя заявочка одобрена" if status == "approved" else "Твою заявочку отклонили"
    icon = EMOJI_CHECK if status == "approved" else EMOJI_CROSS
    return f"{icon} <b>{title}</b>\n\n{escape(note)}"


def admin_stats_text(row) -> str:
    return (
        f"<b>{EMOJI_STATS} Админ панель</b>\n\n"
        f"{EMOJI_PEOPLE} Пользователей всего: <b>{row['users_total']}</b>\n"
        f"{EMOJI_PERSON_OK} Активных для рассылки: <b>{row['users_active']}</b>\n"
        f"{EMOJI_MEGAPHONE} Жалоб: <b>{row['complaints_total']}</b>\n"
        f"{EMOJI_FILE} Анкет: <b>{row['applications_total']}</b>\n"
        f"{EMOJI_CLOCK} На рассмотрении: <b>{row['tickets_active']}</b>"
    )
