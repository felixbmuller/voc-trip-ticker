import logging
import os

import requests
from bs4 import BeautifulSoup as BS
from telegram.ext import Updater, CommandHandler, CallbackContext
from telegram import ParseMode
from dotenv import load_dotenv
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy import create_engine

from templates import (
    merge_date_title,
    telegram_error_message,
    telegram_new_trip,
    telegram_start_command,
    telegram_updated_trip,
)
from database import (
    Trip,
    extract_relevant_trips,
    get_connector,
    save_new_trips,
    setup_database,
    update_updated_trips,
)

# Set constants and load environment variables

AGENDA_URL = "https://www.ubc-voc.com/tripagenda/upcoming.php"
BASE_URL = "https://www.ubc-voc.com"

load_dotenv()

DATABASE_URL = os.environ["VOCTT_DATABASE_URL"]
BOT_TOKEN = os.environ["VOCTT_BOT_TOKEN"]
CHANNEL_NAME = os.environ["VOCTT_CHANNEL_NAME"]
MAINTAINER_CHAT_ID = os.environ["VOCTT_MAINTAINER_CHAT_ID"]
POLLING_INTERVAL = int(os.environ["VOCTT_POLLING_INTERVAL"])  # seconds

# Setup logging

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s [%(levelname)s]: %(message)s"
)

logger = logging.getLogger(__name__)

# Connect to database

engine = create_engine(DATABASE_URL)

session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

# Create tables if not existing
setup_database(Session)


# Function definitions (Telegram bot is started below)


def parse_agenda():
    """extract all events from the VOC trip agenda in a machine readable way"""

    r = requests.get(AGENDA_URL)
    r.raise_for_status()

    bs = BS(r.text, "html.parser")

    events = bs.find_all("tr")

    parsed = []

    for event in events:

        event_parts = event.find_all("td")
        event_data = Trip(
            BASE_URL + event.find("a").get("href"),
            event_parts[0].text,
            event_parts[1].text,
            merge_date_title(event_parts[0].text, event_parts[1].text),
        )

        parsed.append(event_data)

    logger.debug(f"Extracted {len(parsed)} trips from trip agenda")

    return parsed


def report_error(context: CallbackContext, error: Exception, msg: str = ""):
    error_msg = telegram_error_message(error, msg)

    context.bot.send_message(
        chat_id=MAINTAINER_CHAT_ID,
        text=error_msg,
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    logger.error(error_msg)


def polling_handler(context: CallbackContext):

    try:
        trips = parse_agenda()
    except Exception as e:
        report_error(context, e, "Exception while reading trip agenda")
        return

    try:
        new_trips, updated_trips = extract_relevant_trips(Session, trips)
    except Exception as e:
        report_error(context, e, "Exception while comparing trips to database")
        return

    try:

        for trip in new_trips:
            context.bot.send_message(
                chat_id=CHANNEL_NAME,
                text=telegram_new_trip(trip),
                parse_mode=ParseMode.MARKDOWN_V2,
            )

        for trip in updated_trips:
            context.bot.send_message(
                chat_id=CHANNEL_NAME,
                text=telegram_updated_trip(trip),
                parse_mode=ParseMode.MARKDOWN_V2,
            )

    except Exception as e:
        report_error(
            context,
            e,
            f"Exception while trying to send {new_trips=} and {updated_trips=}",
        )
        return

    try:
        save_new_trips(Session, new_trips)
        update_updated_trips(Session, updated_trips)
    except Exception as e:
        report_error(context, e, "Exception while updating the database")


def start_handler(update, context: CallbackContext):
    """hook for /start"""
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=telegram_start_command(CHANNEL_NAME),
    )


# Setup Telegram bot

updater = Updater(token=BOT_TOKEN, use_context=True)

updater.dispatcher.add_handler(CommandHandler("start", start_handler))
updater.job_queue.run_repeating(polling_handler, interval=POLLING_INTERVAL, first=10)

logger.info(
    f"Setup telegram handler and started polling every {POLLING_INTERVAL} seconds"
)

updater.start_polling()
updater.idle()

logger.info("Bot started")

# you can now use some_session to run multiple queries, etc.
# remember to close it when you're finished!
#Session.remove()