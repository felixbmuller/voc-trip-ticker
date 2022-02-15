from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Trip:
    link: str
    date_title: str
    old_date_title: str = ""


def extract_relevant_trips(conn, parsed_trips: list[Trip]):

    new_trips = []
    updated_trips = []


    for trip in parsed_trips:

        data = conn.execute(
            "SELECT * FROM known_trips WHERE link=:link;", **vars(trip)
        ).fetchone()
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

    logger.debug(
        f"Found the following new and updated trips: {new_trips=}, {updated_trips=}"
    )

    return new_trips, updated_trips


def save_new_trips(conn, new_trips: list[dict]):

    for t in new_trips:
        conn.execute(
            "INSERT INTO known_trips (link, date_title) VALUES (:link, :date_title);",
            **vars(t),
        )

    logger.debug(f"Committed {len(new_trips)} inserts.")


def update_updated_trips(conn, updated_trips: list[dict]):


    for t in updated_trips:

        conn.execute(
            "UPDATE known_trips SET date_title=:date_title WHERE link=:link;",
            **vars(t),
        )

    logger.debug(f"Committed {len(updated_trips)} updates.")


def setup_database(conn):


    conn.execute(
        "CREATE TABLE IF NOT EXISTS known_trips (id INTEGER PRIMARY KEY, link varchar, date_title varchar);"
    )

    logger.info("Created database")
