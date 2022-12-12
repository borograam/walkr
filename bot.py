import datetime
import html
import json
import logging
import traceback
from zoneinfo import ZoneInfo

import aiohttp
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
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

DEVELOPER_CHAT_ID = 163127202


# todo: error logger handler to my telegram in pm
# todo: metrics of answer timings. may be make grafana/kibana?


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")


async def get_lab_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info('processing get_epic_info from %s (id=%s) in chat id=%s (message date is %s)', update.effective_user.name, update.effective_user.id, update.effective_chat.id, update.message.date)
    session = context.bot_data['aiohttp_session']
    result = await api.get_lab_info(config.WALKR_TOKEN, session)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=result)


async def get_epic_info(update: Update, context: ContextTypes.DEFAULT_TYPE, callback=False):
    # todo: cron job to autoupdate info in last message of each chat
    # todo: send in markdown
    logger.info('processing get_epic_info from %s (id=%s) in chat id=%s (message date is %s)', update.effective_user.name, update.effective_user.id, update.effective_chat.id, update.message.date)
    if not callback:
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

    if query.data == 'update':
        session = context.bot_data['aiohttp_session']
        result = await api.get_epic_info(config.WALKR_TOKEN, session)
    else:
        result = ('Обработка кнопок под этим сообщением поломалась, запросите новое сообщение и пользуйтесь кнопками '
                  'под ним')

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


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # Finally, send the message
    await context.bot.send_message(
        chat_id=DEVELOPER_CHAT_ID, text=message, parse_mode=ParseMode.HTML
    )


def main():
    application = ApplicationBuilder().token(config.TELEGRAM_TOKEN).post_init(post_init).post_shutdown(
        post_shutdown).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('get_lab_info', get_lab_info))
    application.add_handler(CommandHandler('get_epic_info', get_epic_info))
    application.add_handler(CallbackQueryHandler(callback_query))

    application.add_error_handler(error_handler)

    # todo: /note command to log something

    application.run_polling()


if __name__ == '__main__':
    main()
