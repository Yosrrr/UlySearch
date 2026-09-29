"""Dates des listings UNDP : Posted et Deadline.

Parse uniquement les formats explicitement reconnus.
Ne déduit jamais le rôle d'une date selon qu'elle est passée ou future.
Aucun accès réseau ou base de données.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

DATE_TOKEN = r"\d{1,2}-[A-Za-z]{3}-(?:\d{4}|\d{2})\b"

POSTED_RE = re.compile(
    rf"\bPosted\s*:?\s*(?P<date>{DATE_TOKEN})",
    re.IGNORECASE,
)

DEADLINE_RE = re.compile(
    rf"\bDeadline\s*:?\s*(?P<date>{DATE_TOKEN})"
    r"(?:\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})"
    r"\s*(?P<period>AM|PM)\b"
    r"(?:\s*\((?P<zone>[^)]+)\))?)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class UNDPDates:
    publication_date: date | None
    deadline_date: date | None
    deadline_utc: datetime | None


def _parse_calendar_date(value: str) -> date | None:
    try:
        day_text, month_text, year_text = value.split("-")

        year = int(year_text)

        # Convention explicite pour les annonces contemporaines UNDP.
        if len(year_text) == 2:
            year += 2000

        month = MONTHS[month_text.lower()]
        return date(year, month, int(day_text))

    except (ValueError, KeyError):
        return None


def _new_york_to_utc(local_time: datetime) -> datetime | None:
    """
    Refuse un horaire inexistant ou ambigu lors d'un changement
    d'heure, plutôt que de choisir silencieusement un instant.
    """
    zone = ZoneInfo("America/New_York")
    candidates = set()

    for fold in (0, 1):
        candidate = local_time.replace(
            tzinfo=zone,
            fold=fold,
        ).astimezone(UTC)

        round_trip = candidate.astimezone(zone).replace(tzinfo=None)

        if round_trip == local_time:
            candidates.add(candidate)

    if len(candidates) != 1:
        return None

    return candidates.pop()


def extract_undp_dates(context: str) -> UNDPDates:
    context = " ".join((context or "").split())

    publication = None
    deadline_date = None
    deadline_utc = None

    posted_match = POSTED_RE.search(context)
    if posted_match:
        publication = _parse_calendar_date(
            posted_match.group("date")
        )

    deadline_match = DEADLINE_RE.search(context)

    if deadline_match:
        deadline_date = _parse_calendar_date(
            deadline_match.group("date")
        )

        hour_text = deadline_match.group("hour")
        zone_text = " ".join(
            (deadline_match.group("zone") or "").lower().split()
        )

        # Sans heure ou sans fuseau reconnu :
        # conserver la date, mais ne pas inventer d'instant.
        if (
            deadline_date is not None
            and hour_text is not None
            and zone_text == "new york time"
        ):
            hour = int(hour_text)
            minute = int(deadline_match.group("minute"))
            period = deadline_match.group("period").upper()

            if 1 <= hour <= 12 and 0 <= minute <= 59:
                hour = hour % 12
                if period == "PM":
                    hour += 12

                local_time = datetime(
                    deadline_date.year,
                    deadline_date.month,
                    deadline_date.day,
                    hour,
                    minute,
                )

                deadline_utc = _new_york_to_utc(local_time)

    return UNDPDates(
        publication_date=publication,
        deadline_date=deadline_date,
        deadline_utc=deadline_utc,
    )