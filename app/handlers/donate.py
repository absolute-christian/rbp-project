from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from app.emojis import EMOJI_CHECK

router = Router(name="donate")


@router.callback_query(F.data == "delete_post_pay")
async def cb_delete_post_pay(cb: CallbackQuery) -> None:
    amount = 50
    await cb.bot.send_invoice(
        chat_id=cb.message.chat.id,
        title="удаление поста",
        description="удаление поста проверки",
        payload=f"delete_post:{cb.from_user.id}:{amount}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="50 Stars", amount=amount)],
    )
    await cb.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    await message.answer(f"{EMOJI_CHECK} <b>Оплата прошла</b>")
