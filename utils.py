from aiogram import types
from aiogram.filters import CommandStart, Command, Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    KeyboardButton,
    Message
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
import random


async def global_command_filter(message: Message, state: FSMContext) -> bool:
    ALLOWED_COMMANDS = ["/cancel_trade", "/sent_wallet"]
    current_state = await state.get_state()
    is_command = any(entity.type == 'bot_command' for entity in (message.entities or []))

    if current_state is not None and is_command:
        if message.text.split()[0] in ALLOWED_COMMANDS:  # Check if the command is in the allowed list
            return True
        else:
            await message.reply("You are currently in a deal creation process. Use /cancel_trade to exit.")
            return False
    return True


class GroupChatFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        return message.chat.type in ['group', 'supergroup']


class RoleFilter(Filter):
    def __init__(self, role_needed, collection) -> None:
        self.role_needed = role_needed
        self.collection = collection

    async def __call__(self, callback: types.CallbackQuery, state: FSMContext) -> bool:
        # Assuming the username from Telegram's callback query
        username = callback.from_user.username

        # Dynamically create the field name based on the role_needed
        user_role_field = f"{self.role_needed}'s Telegram User"

        # Construct the query to find if an active deal exists for this user in the specified role
        query = {user_role_field: username, "Status": "Active"}

        # Execute the query
        deal_exists = await self.collection.find_one(query)

        # Return True if a document was found, indicating an active deal exists for the user in the specified role
        return bool(deal_exists)


async def generate_unique_id(collection, max_value=9999):
    # Generates a unique ID for a deal, ensuring no active deal has the same ID.
    unique_id = random.randint(1, max_value)
    # Check if the ID is unique among active deals
    while await collection.find_one({'unique_id': unique_id, 'Status': 'Active'}):
        unique_id = random.randint(1, max_value)
    return unique_id


async def button_builder(text_list: list, callback: list, ) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for text in range(len(text_list)):
        builder.add(types.InlineKeyboardButton(
            text=text_list[text],
            callback_data=callback[text])
        )
    return builder


async def get_data_from_db(deal_data: dict, collection_lobby):
    unique_id = deal_data.get("unique_id")
    deal = await collection_lobby.find_one({"unique_id": unique_id, "Status": "Active"})
    return deal
