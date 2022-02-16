"""Main entry point, run this file to start the bot. Contains the bot logic and setup stuff."""

import logging
import os


from telegram.ext import Updater, CommandHandler, CallbackContext
from dotenv import load_dotenv
from sqlalchemy import create_engine

from templates import (
    telegram_error_message,
    telegram_new_trip,
    telegram_start_command,
    telegram_updated_trip,
)
from database import (
    extract_relevant_trips,
    save_new_trips,
    setup_database,
    update_updated_trips,
)
from scraper import parse_agenda

# Set constants and load environment variables


load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
BOT_TOKEN = os.environ["VOCTT_BOT_TOKEN"]
CHANNEL_NAME = os.environ["VOCTT_CHANNEL_NAME"]
MAINTAINER_CHAT_ID = os.environ["VOCTT_MAINTAINER_CHAT_ID"]
POLLING_INTERVAL = int(os.environ["VOCTT_POLLING_INTERVAL"])  # seconds
LOG_LEVEL = os.environ["VOCTT_LOG_LEVEL"]

# Setup logging

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s [%(levelname)s]: %(message)s"
)

logger = logging.getLogger(__name__)

# Connect to database

engine = create_engine(DATABASE_URL)

# Create tables if not existing
with engine.connect() as conn:
    setup_database(conn)


# Bot event handlers (Telegram bot is started below)


def report_error(context: CallbackContext, error: Exception, msg: str = ""):
    error_msg = telegram_error_message(error, msg)

    context.bot.send_message(
        chat_id=MAINTAINER_CHAT_ID,
        text=error_msg,
    )
    logger.error(error_msg)


def polling_handler(context: CallbackContext):

    with engine.connect() as conn:

        try:
            trips = parse_agenda()
        except Exception as e:
            report_error(context, e, "Exception while reading trip agenda")
            return

        try:
            new_trips, updated_trips = extract_relevant_trips(conn, trips)
        except Exception as e:
            report_error(context, e, "Exception while comparing trips to database")
            return

        # If there are many new trips (this should only happen after a database reset/downtime),
        # we must avoid sending to many messages, otherwise the Telegram API will throw an error.

        if len(new_trips) > 3:
            new_trips = new_trips[:3]
            report_error(context, ValueError("Too many new trips, only showing 3"))

        if len(updated_trips) > 3:
            updated_trips = updated_trips[:3]
            report_error(context, ValueError("Too many updated trips, only showing 3"))

        try:

            for trip in new_trips:
                context.bot.send_message(
                    chat_id=CHANNEL_NAME,
                    text=telegram_new_trip(trip),
                )

            for trip in updated_trips:
                context.bot.send_message(
                    chat_id=CHANNEL_NAME,
                    text=telegram_updated_trip(trip),
                )
            pass

        except Exception as e:
            report_error(
                context,
                e,
                f"Exception while trying to send {new_trips=} and {updated_trips=}",
            )
            return

        try:
            save_new_trips(conn, new_trips)
            update_updated_trips(conn, updated_trips)
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
