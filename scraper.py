"""Scraper for extracting data from the VOC website"""

import logging

import requests
from bs4 import BeautifulSoup as BS

from database import Trip
from templates import merge_date_title

AGENDA_URL = "https://www.ubc-voc.com/tripagenda/upcoming.php"
BASE_URL = "https://www.ubc-voc.com"

logger = logging.getLogger(__name__)


def parse_agenda() -> list[Trip]:
    """extract all events from the VOC trip agenda in a machine readable way.

    Returns
    -------
    list[Trip]
        all trips present in the trip agenda
    """

    r = requests.get(AGENDA_URL)
    r.raise_for_status()

    bs = BS(r.text, "html.parser")

    content = bs.find(id="content")

    parsed = []

    # Merge all headlines (which are months) with the corresponding tables. Skip the first table
    # because it is invisible and just used for padding
    for h3, table in zip(content.find_all("h3"), content.find_all("table")[1:]):

        month = h3.text
        events = table.find_all("tr")

        for event in events:

            event_parts = event.find_all("td")
            event_data = Trip(
                BASE_URL + event.find("a").get("href"),
                merge_date_title(event_parts[0].text, event_parts[1].text, month),
            )

            parsed.append(event_data)

    logger.debug(f"Extracted {len(parsed)} trips from trip agenda")

    return parsed
