from aiogram.fsm.state import State, StatesGroup


class UserRegistration(StatesGroup):
    awaiting_form_submit = State()
    awaiting_deal_continuation = State()
    awaiting_funds_confirmation = State()
    awaiting_funds_release = State()
    dispute = State()