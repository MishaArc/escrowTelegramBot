from aiogram import Bot, Dispatcher, Router, types, F, html
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command, Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardRemove,
)
from utils import RoleFilter, get_data_from_db, button_builder, global_command_filter, GroupChatFilter, send_divider
from aiogram.enums import ParseMode
from config import collection_lobby, MODERATOR_USER_ID
from states.user_registration import UserRegistration
from aiogram.methods.send_message import SendMessage
from aiogram.methods.export_chat_invite_link import ExportChatInviteLink

deal_commands_router = Router()
deal_commands_router.message.filter(global_command_filter)


@deal_commands_router.message(CommandStart())
async def start(message: types.Message):
    if message.chat.type == "private":
        group_message = (
            "I'm designed to facilitate transactions within a group chat. "
            "Please use me in the designated group chat for initiating and managing deals."
        )
        # If you have a static or known link to the group, you could include it here
        # group_message += "\n\nJoin our group chat here: [Group Link]"
        await message.answer(group_message)
    welcome_message = (
        "Hello! I'm the Escrow Bot, designed to facilitate secure, fast, and automated "
        "peer-to-peer transactions within this group. Here’s how you can get started:\n\n"
        "- Use /new_deal to initiate a new transaction.\n"
        "- Follow the prompts to configure your transaction details.\n\n"
        "Please ensure you understand how the escrow process works before initiating a deal. "
        "Type /help for more commands and information on how to use me."
    )
    await message.answer(welcome_message, parse_mode=ParseMode.HTML)


@deal_commands_router.message(Command("help"))
async def help_command(message: types.Message):
    help_text = """
<b>Help & Commands</b>
Here's a list of commands and how to use them:

/start - Get started with the bot and see introductory information.

/help - Display this help message with detailed instructions and commands.

/new_deal - Start a new transaction. Use this command in a group chat where both parties are present. Follow the prompts to set up the deal.

/cancel_trade - Cancel an ongoing transaction. This command can be used if you need to abort the current deal for any reason.

/sent_wallet [wallet_address] - Submit your wallet address as part of the transaction process. Replace [wallet_address] with your actual wallet address.

/release_funds - Release funds from escrow once the transaction conditions are met. This ensures the seller receives the payment securely.

<b>Using the Bot</b>
1. To initiate a deal, use the /new_deal command in the group chat.
2. Follow the instructions provided by the bot to set up the deal.
3. Both parties will need to confirm the deal details for the transaction to proceed.
4. Use /sent_wallet to provide your cryptocurrency wallet address when prompted.
5. Once the deal is set, and conditions are met, use /release_funds to complete the transaction.

For support or more information, please reach out to the bot administrator or visit our FAQ section.

Remember: Always exercise caution when conducting transactions online. Verify the identity of the other party and ensure you are comfortable with the deal before proceeding.
"""
    await message.answer(help_text, parse_mode=ParseMode.HTML)


@deal_commands_router.message(Command("new_deal"), GroupChatFilter())
async def create_a_lobby(message: Message, state: FSMContext) -> None:
    username = message.from_user.username
    if username.startswith('@'):
        username = username[1:]  # Remove '@' if present at the beginning.
    # Check if the user has an active deal
    active_deal = await collection_lobby.find_one({
        "$or": [
            {"Seller's Telegram User": f"{username}", "Status": "Active"},
            {"Buyer's Telegram User": f"{username}", "Status": "Active"}
        ]
    })

    if active_deal:
        # Inform the user that they have an active deal
        await message.answer("You already have an active deal. Please complete or cancel your "
                             "existing deal before starting a new one.")
        return

    # Proceed with creating a new deal lobby
    reply_keyboard = await button_builder(["Submitted the Form"], ["submitted_form"])

    message_text = (
        "📝 <b>Let's get started with your transaction!</b>\n\n"
        "Please take a moment to fill out the details of your deal in the form linked below. "
        "This information will ensure everything goes smoothly and securely.\n\n"
        "👉 <a href='https://docs.google.com/forms/d/e/1FAIpQLSejcvHsgFE2fhfewtlss6ZpMQphPHYw6-l7k6gmdrjh-9gslw/"
        "viewform?usp=sf_link'>Click here to access the Google Form</a>\n\n"
        "Once you've filled out the form, let me know by clicking the 'I've submitted the form' button or by typing "
        "<i>'I submitted the form'</i>.\n\n"
        "If you need help at any point, don't hesitate to ask!"
    )

    await message.answer(
        message_text,
        reply_markup=reply_keyboard.as_markup(),
        disable_web_page_preview=True,
        parse_mode=ParseMode.HTML
    )


@deal_commands_router.message(Command("sent_wallet"), RoleFilter("Seller", collection_lobby), GroupChatFilter())
async def process_seller_wallet(message: Message, state: FSMContext):
    deal = await collection_lobby.find_one({"Seller's Telegram User": message.from_user.username, "Status": "Active"})
    if deal:

        _, wallet_address = message.text.split(maxsplit=1)

        deal_id = deal.get('unique_id')

        if 'Seller\'s Wallet Address' in deal and deal['Seller\'s Wallet Address']:
            await message.answer("The wallet address has already been stored.")
        else:
            await collection_lobby.update_one(
                {"unique_id": deal_id},  # Filter to match the specific document
                {"$set": {"Seller's Wallet Address": wallet_address}}  # Update
            )
            confirmation_message = (
                "✅ <b>Your wallet address has been saved successfully!</b>\n\n"
                "Please double-check to ensure accuracy:\n"
                f"🔐 Wallet: <code>{wallet_address}</code>\n\n"
                "It's crucial that this wallet is on the <i>same network</i> used for the fund transfer. "
                "If this is incorrect or you need to update the information, please let me know."
            )

            await message.answer(
                confirmation_message,
                parse_mode=ParseMode.HTML
            )

    else:
        await message.answer("No active deal found. Please start a new deal.")


@deal_commands_router.message(Command("cancel_trade"), GroupChatFilter())
async def cancel_trade(message: Message, state: FSMContext):
    username = message.from_user.username
    # Query the database to find an active deal with the user's username as either buyer or seller
    deal = await collection_lobby.find_one(
        {
            "$or": [
                {"Buyer's Telegram User": username},
                {"Seller's Telegram User": username}
            ],
            "Status": "Active"
        }
    )

    if deal:
        deal_id = deal.get('unique_id')
        if deal_id:
            # Mark the deal as canceled instead of deleting, for record-keeping
            await collection_lobby.update_one({"unique_id": deal_id}, {"$set": {"Status": "Canceled"}})
            await message.answer("Your deal has been canceled.", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer("No active deal found to cancel.")

    # Now, reset the user's state, if any
    if await state.get_state():
        await state.clear()
        await message.answer("Your current action has been reset.")


@deal_commands_router.message(Command("dispute"), GroupChatFilter())
async def dispute_solver(message: types.Message, state: FSMContext) -> None:
    args = message.get_args().split()

    if not args:
        await message.reply("Please provide the unique ID of the deal you wish to dispute. Usage: /dispute <unique_id>")
        return

    unique_id = args[0]

    deal = await collection_lobby.find_one({"unique_id": unique_id, "Status": "Active"})

    if not deal:
        await message.reply("No active deal found with the provided unique ID.")
        return

    username = message.from_user.username
    if username.startswith('@'):
        username = username[1:]

    if deal["Seller's Telegram User"].lstrip('@') != username and deal["Buyer's Telegram User"].lstrip('@') != username:
        await message.reply("You are not a part of this deal.")
        return

    if deal["Status"] == "Disputed":
        await message.reply("This deal is already under dispute.")
        return

    await collection_lobby.update_one({"unique_id": unique_id}, {"$set": {"Status": "Disputed"}})

    # Generate the invite link for the group chat
    invite_link = await ExportChatInviteLink(chat_id=message.chat.id)

    # Notify the moderator by sending them the invite link directly
    notify_message = (
        f"A dispute has been raised for Deal ID {unique_id} in the group '{message.chat.title}'. "
        f"Please join using this invite link to assist: {invite_link}"
    )
    await SendMessage(chat_id=MODERATOR_USER_ID, text=notify_message)

    # Notify all parties involved in the group chat.
    await message.reply(
        "The dispute has been registered. A moderator has been notified and will join shortly to assist.")
