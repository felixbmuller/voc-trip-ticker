"""Some simple functions to translate machine readable information into strings. All Telegram
templates cap at 4095 because of the maximal message length, but this should never be reached
anyways.
"""

from database import Trip


def merge_date_title(date: str, title: str, month: str):
    return f"{title} · {date} ({month})"


def telegram_new_trip(trip: Trip):
    return f"New Trip: {trip.date_title}\n\n" f"{trip.link}"[:4095]


def telegram_updated_trip(trip: Trip):
    return (
        f"Trip Changed: {trip.date_title}\n\n"
        f"Was: {trip.old_date_title}\n\n"
        f"{trip.link}"
    )[:4095]


def telegram_start_command(channel_name: str):
    return f"Hi, I am the VOCTrip bot. Follow {channel_name} to get updates whenever a new VOC trip is posted"


def telegram_error_message(e: Exception, msg: str):
    return f"Error: {msg}\n\n{type(e).__name__}: {e}"[:4095]
