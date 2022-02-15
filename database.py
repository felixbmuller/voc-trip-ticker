from dataclasses import dataclass
import logging
import sqlite3
import threading

import psycopg2

logger = logging.getLogger(__name__)


@dataclass
class Trip:
    link: str
    date: str
    title: str
    date_title: str
    old_date_title: str = ""

connector_dict = {}

def get_connector(db_url: str):
    """get connector object for the current thread, create it if necessary. A connector object is 
    needed for calling all other functions in this file.
    
    I really don't like that situation, but telegram's JobQueue uses multi-threading and I need 
    different objects for every thread. The parametrization by `db_url` is only there because it 
    feels wrong not to do it, there should never be multiple `db_url`'s"""

    thread_id = threading.get_ident()

    if (db_url, thread_id) not in connector_dict:
        # either SQLite for development or Postgres for production is supported
        if db_url.endswith(".sqlite"):
            connector_dict[(db_url, thread_id)] = sqlite3.connect(db_url)
            logger.info(f"Connected sucessfully to {db_url} by SQLite for thread {thread_id}")
        else:
            connector_dict[(db_url, thread_id)] = psycopg2.connect(db_url)
            logger.info(f"Connected sucessfully to {db_url} by PostgreSQL")

    return connector_dict[(db_url, thread_id)]



def extract_relevant_trips(conn, parsed_trips: list[Trip]):

    new_trips = []
    updated_trips = []

    cur = conn.cursor()

    for trip in parsed_trips:

        cur.execute("SELECT * FROM known_trips WHERE link='%s';", (trip.link,))
        data = cur.fetchone()
        if not data:
            # new trip, not previously in the data
            new_trips.append(trip)
        else:
            _, _, date_title = data  # unpack row
            if date_title != trip.date_title:
                # updated trip
                trip.old_date_title = date_title
                updated_trips.append(trip)
        # if it is an old trip that is not updated -> do nothing

    cur.close

    logger.debug(
        f"Found the following new and updated trips: {new_trips=}, {updated_trips=}"
    )

    return new_trips, updated_trips


def save_new_trips(conn, new_trips: list[dict]):

    cur = conn.cursor()

    for t in new_trips:
        cur.execute(
            "INSERT INTO known_trips (link, date_title) VALUES ('%s', '%s');",
            (t.link, t.date_title),
        )

    conn.commit()
    cur.close()
    logger.debug(f"Committed {len(new_trips)} inserts.")


def update_updated_trips(conn, updated_trips: list[dict]):

    cur = conn.cursor()

    for t in updated_trips:

        cur.execute(
            "UPDATE known_trips SET date_title='%s' WHERE link='%s';",
            (t.date_title, t.link),
        )

    conn.commit()
    cur.close()
    logger.debug(f"Committed {len(updated_trips)} updates.")


def setup_database(conn):
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS known_trips (id serial PRIMARY KEY, link varchar, date_title varchar);"
    )

    conn.commit()
    cur.close()
    logger.info("Created database")
