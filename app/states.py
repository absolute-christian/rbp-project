from aiogram.fsm.state import State, StatesGroup


class ComplaintForm(StatesGroup):
    waiting_for_body = State()


class ApplicationForm(StatesGroup):
    waiting_for_body = State()


class ApplicationDecisionForm(StatesGroup):
    waiting_for_note = State()


class DeletePostForm(StatesGroup):
    waiting_for_link = State()


class BroadcastForm(StatesGroup):
    waiting_for_text = State()
    waiting_for_media = State()
    waiting_for_btn_text = State()
    waiting_for_btn_url = State()
