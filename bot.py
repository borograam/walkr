import datetime
import logging
from zoneinfo import ZoneInfo

import aiohttp
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, Application, CallbackQueryHandler

import api
import config

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# todo: error logger handler to my telegram in pm
# todo: metrics of answer timings. may be make grafana/kibana?


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")


async def get_lab_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info('processing get_epic_info from %s (id=%s) in chat id=%s (message date is %s)', update.effective_user.name, update.effective_user.id, update.effective_chat.id, update.message.date)
    session = context.bot_data['aiohttp_session']
    result = await api.get_lab_info(config.WALKR_TOKEN, session)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=result)


async def get_epic_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # todo: cron job to autoupdate info in last message of each chat
    # todo: pin message only if i can unpin the previous
    # todo: send in markdown
    logger.info('processing get_epic_info from %s (id=%s) in chat id=%s (message date is %s)', update.effective_user.name, update.effective_user.id, update.effective_chat.id, update.message.date)
    await update.effective_chat.send_chat_action('typing')

    session = context.bot_data['aiohttp_session']
    result = await api.get_epic_info(config.WALKR_TOKEN, session)

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Обновить", callback_data="update")]])
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=result,
                                   disable_notification=True,
                                   reply_markup=reply_markup)


async def callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info('processing callback_query id=%s from %s (id=%s) in chat id=%s (message id=%s, data=%s)',
                update.callback_query.id,
                update.effective_user.name, update.effective_user.id, update.effective_chat.id,
                update.callback_query.message.id, update.callback_query.data)

    query = update.callback_query
    assert query.data == 'update'

    session = context.bot_data['aiohttp_session']
    result = await api.get_epic_info(config.WALKR_TOKEN, session)

    await query.answer()

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Обновить", callback_data="update")]])
    now = datetime.datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime('%d.%m.%Y %H:%M:%S')
    updated_text = f'Обновлено пользователем {update.effective_user.name} в {now} MSK'
    await query.edit_message_text(text=f'{result}\n\n{updated_text}', reply_markup=reply_markup)


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
    application.add_handler(CallbackQueryHandler(callback_query))

    # todo: /note command to log something
    # todo: error handler

    application.run_polling()


if __name__ == '__main__':
    main()
