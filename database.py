"""Functions for fetching, storing and updating trips in the database. All functions require a
SQLAlchemy Connection object to work."""

from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Trip:
    """Represent one VOC trip. Date and title is preformatted into a single string for easier
    handling. `old_date_title` is only set on updated trips.
    """
    link: str
    date_title: str
    old_date_title: str = ""


def extract_relevant_trips(conn, parsed_trips: list[Trip]) -> tuple[list[Trip], list[Trip]]:
    """Compare the scraped trips with the database and return all new (link not present in the database) and updated (different description in the database) trips.

    Parameters
    ----------
    conn : Connection
        SQLAlchemy database connection
    parsed_trips : list[Trip]
        all trips scraped from the trip agenda

    Returns
    -------
    list[Trip]
        new trips
    list[Trip]
        updated trips (i.e. date or title changed)
    """

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


def save_new_trips(conn, new_trips: list[Trip]):
    """Store the given list of new trips in the database.

    Parameters
    ----------
    conn : Connection
        SQLAlchemy database connection
    new_trips : list[Trip]
        trips to insert
    """

    for t in new_trips:
        conn.execute(
            "INSERT INTO known_trips (link, date_title) VALUES (:link, :date_title);",
            **vars(t),
        )

    logger.debug(f"Committed {len(new_trips)} inserts.")


def update_updated_trips(conn, updated_trips: list[Trip]):
    """Update the given list of changed trips in the database.

    Parameters
    ----------
    conn : Connection
        SQLAlchemy database connection
    updated_trips : list[Trip]
        trips to update
    """


    for t in updated_trips:

        conn.execute(
            "UPDATE known_trips SET date_title=:date_title WHERE link=:link;",
            **vars(t),
        )

    logger.debug(f"Committed {len(updated_trips)} updates.")


def setup_database(conn):
    """Create the database table if it does not already exist.

    Parameters
    ----------
    conn : Connection
        SQLAlchemy database connection
    """


    conn.execute(
        "CREATE TABLE IF NOT EXISTS known_trips (id INTEGER PRIMARY KEY, link varchar, date_title varchar);"
    )

    logger.info("Created database")
