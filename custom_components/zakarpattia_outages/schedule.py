"""Decode published hourly and half-hourly outages."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from .const import KYIV, QUEUES

HALF_HOUR = timedelta(minutes=30)
ONE_DAY = timedelta(days=1)
HOURS = tuple(str(hour) for hour in range(1, 25))
HOUR_KEYS = frozenset(HOURS)
SLOT_STATES = {"yes": "00", "no": "11", "first": "10", "second": "01"}

type DailySchedule = dict[str, str]
type PublishedSchedules = dict[date, DailySchedule]


@dataclass(frozen=True)
class Outage:
    """Half-open interval expressed in UTC."""

    start: datetime
    end: datetime


def merge_intervals(intervals: Iterable[Outage]) -> tuple[Outage, ...]:
    """Join consecutive outage slots, including across midnight."""
    combined: list[Outage] = []
    for interval in intervals:
        if combined and combined[-1].end == interval.start:
            combined[-1] = Outage(combined[-1].start, interval.end)
        else:
            combined.append(interval)
    return tuple(combined)


def day_intervals(day: date, slots: str) -> tuple[Outage, ...]:
    """Convert a local schedule to absolute time, including clock changes."""
    start = datetime.combine(day, time.min, KYIV).astimezone(UTC)
    end = datetime.combine(day + ONE_DAY, time.min, KYIV).astimezone(UTC)
    outages = []
    while start < end:
        local = start.astimezone(KYIV)
        slot = local.hour * 2 + local.minute // 30
        following = start + HALF_HOUR
        if slots[slot] == "1":
            outages.append(Outage(start, following))
        start = following
    return merge_intervals(outages)


def _parse_row(row: object) -> str | None:
    if not isinstance(row, dict) or row.keys() != HOUR_KEYS:
        return None
    slots = []
    for hour in HOURS:
        value = row[hour]
        if not isinstance(value, str) or value not in SLOT_STATES:
            return None
        slots.append(SLOT_STATES[value])
    return "".join(slots)


def parse_schedule(payload: object, today: date) -> PublishedSchedules:
    """Read complete rows for all subqueues for today and tomorrow."""
    if not isinstance(payload, dict) or payload.get("regionId") != "Uzhhorod":
        raise ValueError("Unexpected region in the outage feed")
    fact = payload.get("fact")
    if not isinstance(fact, dict) or not isinstance(fact.get("data"), dict):
        raise TypeError("Missing fact.data in the outage feed")

    days: PublishedSchedules = {}
    for stamp, groups in fact["data"].items():
        day = datetime.fromtimestamp(int(stamp), KYIV).date()
        if day not in (today, today + ONE_DAY):
            continue
        if day in days:
            raise ValueError(f"Duplicate schedule date: {day}")
        if not isinstance(groups, dict):
            raise TypeError(f"Invalid schedule for {day}")
        days[day] = {
            queue: slots
            for queue in QUEUES
            if (slots := _parse_row(groups.get(f"GPV{queue}"))) is not None
        }
    return days
