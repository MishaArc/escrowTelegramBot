from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from utils import generate_unique_id
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials


async def insert_user_data(user_id, user_name, collection):
    await collection.update_one(
        {'user_id': user_id},
        {'$set': {'user_name': user_name}},
        upsert=True
    )


async def insert_lobby_data(lobby_id, host_user_id, participants, deal_details, lobbies_collection):
    """
    Insert lobby data into the MongoDB collection.

    :param lobby_id: Unique identifier for the lobby.
    :param host_user_id: The user ID of the lobby host.
    :param participants: A list of participant user IDs.
    :param deal_details: Details about the deal.
    """
    lobby_document = {
        "lobby_id": lobby_id,
        "host_user_id": host_user_id,
        "participants": participants,
        "deal_details": deal_details,
        "created_at": datetime.utcnow()
    }

    result = await lobbies_collection.insert_one(lobby_document)
    return result.inserted_id


async def get_deal_details(username, collection):
    # This query searches for an active deal with the specified username as a seller or buyer
    query = {
        "$or": [
            {"Buyer's Telegram User": username},
            {"Seller's Telegram User": username}
        ],
        "Status": "Active"
    }

    # Execute the query to find the deal
    deal = await collection.find_one(query)

    if deal:
        # Extract the relevant information from the deal
        amount_without_commission = deal.get("Amount of money without commission")
        preferred_transfer_method = deal.get("Preferred Transfer Method")
        unique_id = deal.get("unique_id")
        # Return the extracted information
        return {
            "amount_without_commission": amount_without_commission,
            "preferred_transfer_method": preferred_transfer_method,
            "unique_id": unique_id
        }
    else:
        # If no deal is found, return None or an appropriate message
        return None


async def assign_id_to_user(username, collection):
    unique_id = await generate_unique_id(collection)

    # Update the active deal with the generated unique ID
    result = await collection.update_one(
        {'$or': [{"Seller's Telegram User": username}, {"Buyer's Telegram User": username}], 'Status': 'Active'},
        {'$set': {'unique_id': unique_id}}
    )

    return unique_id if result.modified_count > 0 else None


async def save_transaction_to_db(transaction_data, transactions_collection):
    """
    Asynchronously saves a transaction to the MongoDB database and checks if it already exists.

    :param transaction_data: Dictionary containing transaction details.
    :return: Boolean indicating whether the transaction was new and saved.
    """
    existing_transaction = await transactions_collection.find_one({'walletTxId': transaction_data['walletTxId']})
    if not existing_transaction:
        await transactions_collection.insert_one(transaction_data)
        return True
    return False


async def mark_transaction_as_completed(wallet_tx_id, transactions_collection):
    """
    Marks a transaction as completed in the database.

    :param wallet_tx_id: The wallet transaction ID.
    """
    await transactions_collection.update_one(
        {'walletTxId': wallet_tx_id},
        {'$set': {'completed': True}}
    )
