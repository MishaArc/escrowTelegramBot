import httpx
import asyncio
from aiogram import Router, types, F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    ReplyKeyboardRemove,
)
import logging
from utils import global_command_filter, RoleFilter, button_builder
from wallet_processing import get_incoming_transactions, send_trc20_tokens, collection_trans
from config import collection_lobby
from states.user_registration import UserRegistration

form_router = Router()

form_router.message.filter(global_command_filter)


@form_router.callback_query(F.data == "submitted_form")
async def submitted_form_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    username = callback.from_user.username
    start_time = asyncio.get_event_loop().time()
    found = False
    await callback.message.edit_reply_markup()
    try:
        while (asyncio.get_event_loop().time() - start_time) < (15 * 60):  # 15 minutes
            document = await collection_lobby.find_one({
                "$or": [
                    {"Seller's Telegram User": username},
                    {"Buyer's Telegram User": username}
                ],
                "Status": "Active"
            })
            if document:
                try:

                    seller_document = await collection_lobby.find_one({'$or':
                                                                           [{"Seller's Telegram User": username},
                                                                            {"Buyer's Telegram User": username}],
                                                                       'Status': 'Active'})
                    seller_username = seller_document.get("Seller's Telegram User")
                    unique_id = seller_document.get("unique_id")
                    await state.update_data(unique_id=unique_id, seller=seller_username)
                except Exception as e:
                    logging.error(f"Error updating state data: {e}")
                    await callback.message.answer("There was an error processing your submission. Please try again.")
                    break

                found = True
                await callback.message.answer("Your submission has been confirmed!", reply_markup=ReplyKeyboardRemove())

                rows = ["Seller's Telegram User", "Buyer's Telegram User"]
                deal_data = (
                    "🔍 <b>Deal Confirmation</b>\n"
                    "Please review the details of your transaction carefully:\n\n"
                    f"👤 <b>Seller:</b> {document.get(rows[0], 'Not Provided')}\n"
                    f"👥 <b>Buyer:</b> {document.get(rows[1], 'Not Provided')}\n"
                    f"💳 <b>Payment Method:</b> {document.get('Preferred Transfer Method', 'Not provided')}\n"
                    f"💰 <b>Amount:</b> {document.get('Amount of money without commission', 'Not provided')} USDT\n"
                    f"🆔 <b>Deal ID:</b> {document.get('unique_id', 'Not provided')}\n\n"
                    "This ID is essential for dispute resolution or any further assistance.\n\n"
                    "If all details are correct, please <b>confirm</b> by clicking 'Continue with the deal' below.\n"
                    "To modify any information, use the 'Data is incorrect' button to submit again."
                )

                # Send the deal data to the user
                reply_keyboard = await button_builder(
                    ["The data is incorrect. Submit again", 'Continue with the deal'],
                    ["resubmit_form", "continue_deal"])
                reply_keyboard.adjust(1, 1)
                await callback.message.answer(deal_data,
                                              reply_markup=reply_keyboard.as_markup(),
                                              parse_mode=ParseMode.HTML)

                break
            else:
                await asyncio.sleep(30)

        if not found:
            reply_keyboard = await button_builder(["Retry submission"], ["submitted_form"])
            await callback.message.answer("We could not find your submission. Please submit the form again.",
                                          reply_markup=reply_keyboard.as_markup())

        await state.set_state(UserRegistration.awaiting_deal_continuation)

    except Exception as e:
        logging.exception(f"An error occurred during form submission handling: {e}")
        await callback.message.answer("An unexpected error occurred. Please contact support.")
        await callback.answer()


@form_router.callback_query(F.data == "resubmit_form")
async def handle_incorrect_data_submission(callback: types.CallbackQuery) -> None:
    username = callback.from_user.username

    # Query the database to find an active deal for the user
    deal = await collection_lobby.find_one({
        "$or": [
            {"Buyer's Telegram User": username},
            {"Seller's Telegram User": username}
        ],
        "Status": "Active"
    })

    # If an active deal is found, delete it to allow for resubmission
    if deal:
        await collection_lobby.delete_one({"unique_id": deal['unique_id']})

    # Provide the user with the form link and the button to submit the form
    message_text = (
        "🙇‍♂️ <b>Oops! Looks like we need a bit more info.</b>\n\n"
        "No worries at all! It happens to the best of us. Here’s a quick way to get everything sorted:\n\n"
        "1️⃣ <a href='https://docs.google.com/forms/d/e/1FAIpQLSejcvHsgFE2fhfewtlss6ZpMQphPHYw6-l7k6gmdrjh-9gslw/"
        "viewform?usp=sf_link'>"
        "Click here to revisit the form</a> and fill in the missing or incorrect details.\n\n"
        "2️⃣ Once you’ve made the updates, hit the 'I've submitted the form' button below to let me know. 📬\n\n"
        "Take your time, and if you have any questions or need help along the way, just give me a shout!"
    )

    # Prepare the inline keyboard with the button to confirm form resubmission
    reply_keyboard = await button_builder(["Confirm form resubmission"], ["submitted_form"])

    # Send the message with the inline keyboard
    await callback.message.answer(
        message_text,
        reply_markup=reply_keyboard.as_markup(),
        disable_web_page_preview=True,
        parse_mode=ParseMode.HTML
    )


@form_router.callback_query(F.data == "continue_deal")
async def continue_deal(callback: types.CallbackQuery) -> None:
    username = callback.from_user.username
    user_id = callback.from_user.id

    # Query the database for an active deal involving this user
    deal_details = await collection_lobby.find_one({
        "$or": [
            {"Seller's Telegram User": username},
            {"Buyer's Telegram User": username}
        ],
        "Status": "Active"
    })

    if not deal_details:
        await callback.message.answer("No active deal found associated with your account. Please start a new deal.")
        return

    # Check if the user has already interacted
    if user_id in deal_details.get('users_interacted', []):
        await callback.answer("You have already continued this deal.")
        return

    # Update the deal to mark the user's interaction and increment the count
    new_count = deal_details.get('continue_deal_count', 0) + 1
    await collection_lobby.update_one(
        {"unique_id": deal_details['unique_id']},
        {
            "$set": {"continue_deal_count": new_count},
            "$addToSet": {"users_interacted": user_id}  # Ensures the user ID is added only once
        }
    )

    if new_count < 2:
        await callback.answer("Waiting for the other party to continue the deal.")
    elif new_count == 2:
        # Execute the core functionality for when both parties have continued
        amount_without_commission = float(deal_details.get('Amount of money without commission', 0))
        unique_id_factor = deal_details['unique_id'] * 0.00001
        transfer_amount = amount_without_commission + unique_id_factor
        payment_instructions = (
            "✅ <b>Ready to Transfer Funds</b>\n\n"
            "Here’s how to complete your transaction:\n\n"
            "1️⃣ <b>Transfer the Amount:</b>\n"
            f"   Send exactly <b>{transfer_amount} USDT</b> to the wallet address below.\n"
            f"   <code>TX2yV1F6bD4CYiH6ytA1yLKUrsyaP4Mth4</code>\n\n"
            "2️⃣ <b>Use the Right Network:</b>\n"
            f"   Ensure you are using the <i>{deal_details.get('preferred_transfer_method')}</i> network for the "
            f"transfer.\n\n"
            "3️⃣ <b>Confirmation:</b>\n"
            "   After you've sent the funds, tap the 'Funds Sent' button so we can proceed with the deal.\n\n"
            "🔔 Need help or have questions? Don't hesitate to reach out!"
        )

        reply_keyboard = await button_builder(["Sent funds"], ["sent_funds"])
        await callback.message.answer(payment_instructions,
                                      reply_markup=reply_keyboard.as_markup(),
                                      parse_mode=ParseMode.HTML)
        await callback.answer()  # To notify Telegram that the callback was processed


@form_router.callback_query(F.data == "sent_funds",
                            RoleFilter("Buyer", collection_lobby))
async def sent_funds_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    user_data = await collection_lobby.find_one({
        "$or": [
            {"Buyer's Telegram User": callback.from_user.username},
            {"Seller's Telegram User": callback.from_user.username}
        ],
        "Status": "Active"
    })
    deal_id = user_data.get('unique_id')

    if user_data and callback.from_user.username == user_data["Buyer's Telegram User"]:
        async with httpx.AsyncClient() as client1:
            wallet_tx_id = await get_incoming_transactions(client1)
            if wallet_tx_id and await collection_trans.find_one(
                    {"amount": user_data["Amount of money without commission"] + deal_id * 0.00001,
                     "completed": False}
            ):
                builder = await button_builder(["Release funds"], ["release_funds"])
                message_text = (
                    "✅ <b>Transaction Confirmed!</b>\n\n"
                    "We've successfully located your transaction:\n"
                    f"🔗 <a href='https://tronscan.org/#/transaction/{wallet_tx_id}'>View Transaction</a>\n\n"
                    "What's next?\n"
                    "👉 <b>Seller:</b> You're good to go! Please proceed with delivering the items to the buyer.\n"
                    "👉 <b>Buyer:</b> Once you've received the items and are happy with them, please release the "
                    "funds to the seller. "
                    "You can do this by using the <code>/release_funds</code> command.\n\n"
                    "Need help or have questions along the way? Don't hesitate to reach out!"
                )

                await callback.message.answer(
                    message_text,
                    disable_web_page_preview=True,
                    reply_markup=builder.as_markup(),
                    parse_mode=ParseMode.HTML
                )
            else:
                await callback.answer("<i>No new transactions with that amount found.</i>",
                                      parse_mode=ParseMode.HTML)
    else:
        await callback.answer("<b>You are not authorized to confirm funds receipt.</b>",
                              parse_mode=ParseMode.HTML)
    await state.set_state(UserRegistration.awaiting_funds_release)


@form_router.callback_query(F.data == "release_funds",
                            RoleFilter("Buyer", collection_lobby),
                            )
async def send_random_value(callback: types.CallbackQuery, state: FSMContext) -> None:
    user_data = await collection_lobby.find_one({
        "$or": [
            {"Buyer's Telegram User": callback.from_user.username},
            {"Seller's Telegram User": callback.from_user.username}
        ],
        "Status": "Active"
    })
    unique_id = user_data.get("unique_id")

    if user_data and user_data.get("Seller's Wallet Address"):
        async with httpx.AsyncClient() as client1:
            back_trans = await send_trc20_tokens(client1,
                                                 'TRX',
                                                 user_data.get("Amount of money without commission"),
                                                 recipient_address=user_data.get("Seller's Wallet Address")
                                                 )
            if back_trans:
                complete_trans_db = await collection_trans.find_one(
                    {"amount": user_data.get("Amount of money without commission") + unique_id * 0.00001,
                     "completed": False}
                )

                if complete_trans_db:
                    result = await collection_trans.update_one(
                        {"_id": complete_trans_db["_id"]},
                        {"$set": {"completed": True}}
                    )
                    await collection_lobby.update_one({"unique_id": unique_id, "Status": "Active"},
                                                      {"$set": {"Status": "Inactive"}})
                    if result.modified_count == 1:
                        await callback.message.answer(
                            "<b>Transaction marked as completed.</b>",
                            parse_mode=ParseMode.HTML
                        )
                        await state.clear()
                    else:
                        await callback.message.answer(
                            "<b>Transaction was not updated.</b>",
                            parse_mode=ParseMode.HTML
                        )
            else:
                await callback.message.answer(
                    "<i>No matching transaction found.</i>",
                    parse_mode=ParseMode.HTML
                )
    elif user_data and not user_data.get("Seller's Wallet Address"):
        await callback.message.answer(
            "🚫 <b>Wallet Not Found</b> 🚫\n\n"
            "It seems we don't have a wallet address on file for the seller. No problem, though! Here’s how to fix it:\n\n"
            "👤 <b>Seller:</b> Please submit your wallet address using the command below. Just replace <i>&lt;your wallet&gt;</i> with your actual wallet address.\n\n"
            "💼 <code>/sent_wallet &lt;your wallet&gt;</code>\n\n"
            "For example:\n"
            "<code>/sent_wallet TCdRk63AC8gXH1qPrsesdFXeKLERh9m2ni</code>\n\n"
            "This will ensure we have the correct wallet address for transactions. If you need help or have questions, feel free to reach out!",
            parse_mode=ParseMode.HTML
        )
