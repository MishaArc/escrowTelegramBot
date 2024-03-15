import httpx
import asyncio
import json
import base64
import hashlib
import hmac
import time
from motor.motor_asyncio import AsyncIOMotorClient
from database.database_utils import save_transaction_to_db
from config import (collection_transactions as collection_trans, kucoin_api_key as api_key,
                    kucoin_api_secret as api_secret,
                    kucoin_api_passphrase as api_passphrase)


base_url = 'https://api.kucoin.com'


def generate_headers(endpoint, method, api_key, api_secret, api_passphrase, body=''):
    """
    Generate the headers needed to authenticate with the KuCoin API.

    :param endpoint: API endpoint (e.g., '/api/v1/accounts').
    :param method: HTTP method ('GET', 'POST', etc.).
    :param api_key: Your KuCoin API key.
    :param api_secret: Your KuCoin API secret.
    :param api_passphrase: Your KuCoin API passphrase.
    :param body: The request body as a string (for POST requests).
    :return: A dictionary containing the headers.
    """

    # Get the current timestamp in milliseconds
    now = int(time.time() * 1000)
    str_to_sign = str(now) + method + endpoint + body

    # Create the signature
    signature = base64.b64encode(
        hmac.new(api_secret.encode(), str_to_sign.encode(), hashlib.sha256).digest()
    )

    # Encode the passphrase
    passphrase = base64.b64encode(
        hmac.new(api_secret.encode(), api_passphrase.encode(), hashlib.sha256).digest()
    )

    # Construct and return the headers
    headers = {
        "KC-API-SIGN": signature,
        "KC-API-TIMESTAMP": str(now),
        "KC-API-KEY": api_key,
        "KC-API-PASSPHRASE": passphrase,
        "KC-API-KEY-VERSION": "2"
    }
    return headers


async def get_incoming_transactions(client):
    transaction = None
    endpoint = '/api/v1/accounts'
    headers = generate_headers(endpoint, 'GET', api_key, api_secret, api_passphrase)
    try:
        accounts_response = await client.get(f'{base_url}{endpoint}', headers=headers)
        accounts_response.raise_for_status()
        accounts = accounts_response.json()

        for account in accounts['data']:
            currency = 'TRX'  # Assuming you want to check for USDT deposits
            account_id = account['id']
            account_address = 'TX2yV1F6bD4CYiH6ytA1yLKUrsyaP4Mth4'
            deposits_endpoint = f'/api/v1/deposits?currency={currency}&status=SUCCESS'
            deposits_headers = generate_headers(deposits_endpoint, 'GET', api_key, api_secret, api_passphrase)
            deposits_response = await client.get(f'{base_url}{deposits_endpoint}', headers=deposits_headers)
            deposits_response.raise_for_status()
            deposits = deposits_response.json()

            if deposits['data']['items']:
                for deposit in deposits['data']['items']:
                    transaction = {
                        'walletTxId': deposit['walletTxId'],
                        'amount': float(deposit['amount']),
                        'currency': deposit['currency'],
                        'account_id': account_id,
                        'completed': False
                    }

                    if await save_transaction_to_db(transaction, collection_trans):
                        print(f"New transaction added: {transaction}")

    except httpx.HTTPError as e:
        print(f"An HTTP error occurred: {e}")
        return None
    return transaction['walletTxId']


async def send_trc20_tokens(client, currency, amount, recipient_address, memo=None):
    """
    Send TRC-20 tokens to a specified address using KuCoin API.
    :param client: HTTP client for making requests.
    :param currency: Currency code (e.g., 'USDT').
    :param amount: Amount to send.
    :param recipient_address: Recipient's TRC-20 address.
    :param memo: Memo for the transaction (if needed).
    :return: Response from the API call.
    """
    endpoint = '/api/v1/withdrawals'
    body = json.dumps({
        "currency": currency,
        "amount": amount,
        "address": recipient_address,

        "memo": memo  # Optional
    })
    headers = generate_headers(endpoint, 'POST', api_key, api_secret, api_passphrase, body)
    headers['Content-Type'] = 'application/json'
    response = await client.post(f'{base_url}{endpoint}', headers=headers, data=body)
    return response.json()


async def main():
    async with httpx.AsyncClient() as client:
        while True:
            await get_incoming_transactions(client)
            await asyncio.sleep(60)  # Sleep for 1 minute


if __name__ == "__main__":
    asyncio.run(main())
