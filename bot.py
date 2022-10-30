import logging

import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, Application

import api
import config

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# todo: error handler to my telegram in pm


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")


async def get_lab_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = context.bot_data['aiohttp_session']
    result = await api.get_lab_info(config.WALKR_TOKEN, session)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=result)


async def get_epic_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = context.bot_data['aiohttp_session']
    result = await api.get_epic_info(config.WALKR_TOKEN, session)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=result)


async def post_init(application: Application):
    session = aiohttp.ClientSession(trust_env=True)
    application.bot_data['aiohttp_session'] = session


async def post_shutdown(application: Application):
    session = application.bot_data['aiohttp_session']
    await session.close()


def main():
    application = ApplicationBuilder().token(config.TELEGRAM_TOKEN).post_init(post_init).post_shutdown(
        post_shutdown).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('get_lab_info', get_lab_info))
    application.add_handler(CommandHandler('get_epic_info', get_epic_info))

    application.run_polling()


if __name__ == '__main__':
    main()
