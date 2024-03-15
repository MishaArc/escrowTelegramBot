from dotenv import load_dotenv
import os
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()
uri = os.getenv("URI")
client = AsyncIOMotorClient(uri, tlsAllowInvalidCertificates=True)
db = client[os.getenv("MONGO_DB_NAME")]
collection_lobby = db[os.getenv("COLLECTION_NAME")]

db_transactions = client[os.getenv("MONGO_DB_TRANSACTION")]
collection_transactions = db_transactions[os.getenv("COLLECTION_NAME_TRANSACTION")]

TOKEN = os.getenv('TOKEN')

sheety_api_url = os.getenv("SHEETY_URL")
sheety_token = os.getenv("SHEETY_ID")

MODERATOR_USER_ID = os.getenv("MODERATOR_USER_ID")

kucoin_api_key = os.getenv("KUCOIN_API_KEY")
kucoin_api_secret = os.getenv("KUCOIN_API_SECRET")
kucoin_api_passphrase = os.getenv("KUCOIN_API_PASSPHRASE")