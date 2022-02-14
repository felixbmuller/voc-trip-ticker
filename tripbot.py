from webbrowser import get
import requests
from bs4 import BeautifulSoup as BS
import os
import psycopg2
from telegram.ext import Updater, CommandHandler, CallbackContext
from telegram import ParseMode

AGENDA_URL = "https://www.ubc-voc.com/tripagenda/upcoming.php"
BASE_URL = "https://www.ubc-voc.com"

DATABASE_URL = "placeholder"
BOT_TOKEN = "placeholder"
CHANNEL_NAME = "@voctripticker"

POLLING_INTERVAL = 60  # seconds

conn = psycopg2.connect(DATABASE_URL)


def parse_agenda():
    """extract all events from the VOC trip agenda in a machine readable way"""

    r = requests.get(AGENDA_URL)
    r.raise_for_status()

    bs = BS(r.text, "html.parser")

    events = bs.find_all("tr")

    parsed = []

    for event in events:

        event_parts = event.find_all("td")
        event_data = {
            "date": event_parts[0].text,
            "title": event_parts[1].text,
            "link": BASE_URL + event.find("a").get("href"),
        }

        parsed.append(event_data)

    return parsed


def extract_relevant_trips(parsed_trips: list[dict]):

    cur = conn.cursor()

    cur.execute("SELECT * FROM known_trips;")
    links = set(link for _, link in cur.fetchall())

    new_trips = [t for t in parsed_trips if t["link"] not in links]

    cur.close()
    return new_trips


def save_new_trips(new_trips: list[dict]):

    cur = conn.cursor()

    for t in new_trips:
        cur.execute("INSERT INTO known_trips (link) VALUES (%s);", (t["link"],))

    conn.commit()
    cur.close()


def polling_handler(context: CallbackContext):

    trips = parse_agenda()
    new_trips = extract_relevant_trips(trips)

    for trip in new_trips:
        context.bot.send_message(
            chat_id=CHANNEL_NAME,
            text=(
                f"New Trip: *{trip['title']}* (_{trip['date']}_)\n\n"
                f"[{trip['link']}]({trip['link']})"
            ),
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    save_new_trips(new_trips)


def start_handler(update, context: CallbackContext):
    """hook for /start"""
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Hi, I am the VOCTrip bot. Follow {CHANNEL_NAME} to get updates whenever a new VOC trip is posted",
    )


def main():

    cur = conn.cursor()

    cur.execute(
        "CREATE TABLE IF NOT EXISTS known_trips (id serial PRIMARY KEY, link varchar);"
    )

    conn.commit()
    cur.close()

    updater = Updater(token=BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    job_queue = updater.job_queue

    dispatcher.add_handler(CommandHandler("start", start_handler))
    updater.start_polling()

    job_queue.run_repeating(polling_handler, interval=POLLING_INTERVAL, first=10)
