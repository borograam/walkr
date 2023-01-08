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

# todo: перенести секреты в venv (вычищать в момент инициализации)
import config
import logic
import orm

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


# todo: metrics of answer timings. may be make grafana/kibana? what about zabbix?
# todo: прикапывать цифры из инфы о лабе, рисовать графики в динамике


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")


async def _get_epic_info(
        update: Update, context: ContextTypes.DEFAULT_TYPE, callback=False
) -> tuple[str, InlineKeyboardMarkup]:
    # todo: cron job to autoupdate info in last message of each chat
    # todo: send in markdown
    # todo? на сервере генерить изображение с таблицей со всей информацией
    # мысли о мультитокенности: отдельное меню кнопкой "настройки", там:
    # - юзер:
    #   - все доступные (для группы). В процессе работы отправит запрос полностью от всех, исключит дубликаты и
    #     отправляет одним сообщением конкатенацию ответов
    #   - (отдельно имя каждого игрока, для кого есть токен) (для лички)
    # - автообновление (в названии кнопки галка или крестик как текущий стейт)
    # Для обоих вариантов явно надо хранить инфу в sql в разрезе (чат, сообщение)
    logger.info('processing get_epic_info from %s (id=%s) in chat id=%s',
                update.effective_user.name, update.effective_user.id, update.effective_chat.id)
    if not callback:
        await update.effective_chat.send_chat_action('typing')

    http_session = context.bot_data['aiohttp_session']
    with orm.make_session() as session:
        walkr_token = session.query(orm.Token).filter(orm.Token.user_id == 271306).one().value

    result = await logic.get_epic_info(walkr_token, http_session)
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Обновить", callback_data="update_epic_info")]])

    return result, reply_markup


async def get_epic_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result, reply_markup = await _get_epic_info(update, context, callback=False)
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

    if query.data == 'update_epic_info':
        text, reply_markup = await _get_epic_info(update, context, callback=True)

        # todo: вынести в единое место после перехода всего в маркдаун
        now = datetime.datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime('%d.%m.%Y %H:%M:%S')
        updated_text = f'Обновлено пользователем {update.effective_user.name} в {now} MSK'

        edit_message_text_kwargs = {'text': f'{text}\n\n{updated_text}', 'reply_markup': reply_markup}
    elif query.data == 'update_lab_requests':
        text, reply_markup = await _get_lab_requests(update, context, callback=True)
        edit_message_text_kwargs = {'text': text, 'reply_markup': reply_markup, 'parse_mode': ParseMode.MARKDOWN_V2}
    elif query.data == 'make_requests':
        http_session = context.bot_data['aiohttp_session']
        with orm.make_session() as db_session:
            await logic.make_lab_requests(http_session, db_session)

        text, reply_markup = await _get_lab_requests(update, context, callback=True)
        edit_message_text_kwargs = {'text': text, 'reply_markup': reply_markup, 'parse_mode': ParseMode.MARKDOWN_V2}
    else:
        text = ('Обработка кнопок под этим сообщением поломалась, запросите новое сообщение и пользуйтесь кнопками '
                'под ним')
        edit_message_text_kwargs = {'text': text, 'parse_mode': ParseMode.MARKDOWN_V2}

    await query.answer()
    await query.edit_message_text(**edit_message_text_kwargs)


def markdown_escape(text: str) -> str:
    chars = ('_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!')
    for char in chars:
        if char in text:
            text = text.replace(char, f'\\{char}')
    return text


async def _get_lab_requests(
        update: Update, context: ContextTypes.DEFAULT_TYPE, callback=False
) -> tuple[str, InlineKeyboardMarkup]:
    logger.info('start get_lab_requests')
    http_session = context.bot_data['aiohttp_session']

    message_rows = ['Вижу такие запросы в лаборатории:\n']
    with orm.make_session() as session:
        progresses, has_token_no_request_query = await logic.get_current_lab_planets(http_session, session)
        progresses.sort(key=lambda p: p.request.requested_dt, reverse=True)

        for progress in progresses:
            seconds_left = (
                        progress.request.requested_dt.replace(tzinfo=ZoneInfo('utc')) + datetime.timedelta(hours=6) -
                        datetime.datetime.now(tz=ZoneInfo('utc'))).seconds
            message_rows.append(
                f' \\- *{markdown_escape(progress.request.lab_planet.user.name)}* {progress.total_donation}/{progress.request.lab_planet.planet_requirements} осталось {seconds_left // 3600}h{seconds_left % 3600 // 60}m')

        has_token_no_request_count = has_token_no_request_query.count()
        if has_token_no_request_count:
            message_rows.append(markdown_escape('\nСледующим игрокам можно попробовать сделать запрос ботом:\n'))
            for user in has_token_no_request_query:
                message_rows.append(f' \\- *{markdown_escape(user.name)}*')

            message_rows.append(f'_{markdown_escape("(правда, я бессилен в случае, если планета докачана до конца)")}_')

        session.commit()

    now = datetime.datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime('%d.%m.%Y %H:%M:%S')
    if callback:
        message_rows.append(markdown_escape(f'\nОбновлено пользователем {update.effective_user.name} в {now} MSK'))
    else:
        message_rows.append(markdown_escape(f'\nАктуально на {now} MSK'))

    buttons = [InlineKeyboardButton("Обновить", callback_data="update_lab_requests")]
    if has_token_no_request_count:
        buttons.append(InlineKeyboardButton("Делаем запросы", callback_data="make_requests"))

    reply_markup = InlineKeyboardMarkup([buttons])
    return '\n'.join(message_rows), reply_markup


async def get_lab_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, reply_markup = await _get_lab_requests(update, context)
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=text,
                                   disable_notification=True,
                                   reply_markup=reply_markup,
                                   parse_mode=ParseMode.MARKDOWN_V2)


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
    )
    error = html.escape(tb_string)
    messages = [message]
    for x in range(0, len(error), 4096):
        messages.append(f'<pre>{error[x:x + 4096]}</pre>')

    # Finally, send the message
    for m in messages:
        await context.bot.send_message(chat_id=DEVELOPER_CHAT_ID, text=m, parse_mode=ParseMode.HTML)


def main():
    application = ApplicationBuilder().token(config.TELEGRAM_TOKEN).post_init(post_init).post_shutdown(
        post_shutdown).build()

    application.add_handler(CommandHandler('start', start))
    # application.add_handler(CommandHandler('get_lab_info', get_lab_info))
    application.add_handler(CommandHandler('get_epic_info', get_epic_info))
    application.add_handler(CommandHandler('get_lab_requests', get_lab_requests))
    application.add_handler(CallbackQueryHandler(callback_query))

    application.add_error_handler(error_handler)

    # todo: /note command to log something - only after adding some log parsing
    # todo: some command to keep metrics from spaceship mission - only after adding a db
    # todo: logout command, need to add telegram id to user table

    application.run_polling()


if __name__ == '__main__':
    main()
