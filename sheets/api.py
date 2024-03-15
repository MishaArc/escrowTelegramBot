from config import sheety_api_url, collection_lobby as collection, sheety_token
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import aiohttp
from aioscheduler import TimedScheduler

# Database connection parameters
db_params = {
    "user": "your_username",
    "password": "your_password",
    "database": "your_dbname",
    "host": "your_host"
}


async def fetch_data_from_sheet():
    async with aiohttp.ClientSession(trust_env=True) as session:
        async with session.get(sheety_api_url, ssl=False) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('escrowSheetLink', [])  # Ensure we get the list or an empty list if not found
            else:
                response_text = await response.text()
                print(f"Error fetching data: {response.status}")
                print(f"Response body: {response_text}")
                return []


async def insert_data_into_db(data):
    # Define a mapping of old header names to new header names
    header_mapping = {
        "seller'sTelegramUsername": "Seller's Telegram User",
        "buyer'sTelegramUsername": "Buyer's Telegram User",
        "preferredTransferMethod": "Preferred Transfer Method",
        "amountOfMoneyWithoutCommision": "Amount of money without commission",
        "id": "unique_id"
    }

    for row in data:
        # Create a new dictionary for the transformed row
        transformed_row = {}
        for old_key, new_key in header_mapping.items():
            # Use the new header name and copy the value from the old header name
            transformed_row[new_key] = row.get(old_key, None)

        # Add the Status field
        transformed_row['Status'] = 'Active'

        # Insert the transformed document into MongoDB
        await collection.insert_one(transformed_row)


async def delete_row_from_sheet(row_id):
    sheety_delete_url = f"{sheety_api_url}/{row_id}"
    async with aiohttp.ClientSession() as session:

        response = await session.delete(sheety_delete_url, ssl=False)
        if response.status == 204:
            print(f"Row {row_id} deleted successfully.")
        else:
            print(f"Failed to delete row {row_id}. Status code: {response}")


async def job_function():
    print("Fetching and updating database...")
    data = await fetch_data_from_sheet()
    header_mapping = {
        "seller'sTelegramUsername": "Seller's Telegram User",
        "buyer'sTelegramUsername": "Buyer's Telegram User",
        "preferredTransferMethod": "Preferred Transfer Method",
        "amountOfMoneyWithoutCommision": "Amount of money without commission",
        "id": "unique_id"
    }
    for row in data:
        seller_username = row.get("seller'sTelegramUsername")
        buyer_username = row.get("buyer'sTelegramUsername")
        row_id = row.get("id")

        # Check if there's an existing active deal for the seller or buyer
        existed_deal = await collection.find_one({
            "$or": [
                {"Seller's Telegram User": seller_username, "unique_id": row_id},
                {"Buyer's Telegram User": buyer_username, "unique_id": row_id}
            ]
        })
        existing_deal = await collection.find_one({
            "$or": [
                {"Seller's Telegram User": seller_username, "Status": "Active"},
                {"Buyer's Telegram User": buyer_username, "Status": "Active"}
            ]
        })

        if existed_deal:
            print(f"ETO EXISTEd {row_id}, {seller_username} {buyer_username}")
            continue
        elif existing_deal:
            print(row_id)
            await delete_row_from_sheet(row_id)
        else:
            # If no active deal exists, transform and insert the row into MongoDB
            transformed_row = {header_mapping.get(k, k): v for k, v in row.items()}
            transformed_row['Status'] = 'Active'  # Set status to Active for new deals
            await collection.insert_one(transformed_row)


async def scheduler(interval, func):
    while True:
        await func()
        await asyncio.sleep(interval)


async def main():
    # Run the job function every 300 seconds (5 minutes)
    asyncio.create_task(scheduler(120, job_function))

    # Run forever
    while True:
        await asyncio.sleep(3600)  # Sleeps for 1 hour


if __name__ == '__main__':
    asyncio.run(main())
