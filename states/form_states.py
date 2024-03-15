from aiogram.fsm.state import State, StatesGroup


class Form(StatesGroup):
    seller = State()
    buyer = State()
    deal_details = State()
    unique_id = State()
