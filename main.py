import logging
import sys
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from utils import global_command_filter
from handlers.inline_process import form_router
from handlers.commands import deal_commands_router
from config import TOKEN


async def main() -> None:
    bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    dp.message.filter(global_command_filter)
    dp.include_router(form_router)
    dp.include_router(deal_commands_router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
