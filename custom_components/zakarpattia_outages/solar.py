"""Describe civil twilight, daytime, and night using HA's configured location."""

from datetime import date, datetime
from functools import lru_cache
from math import isfinite

from astral import Observer
from astral.sun import dawn, dusk, sunrise, sunset

from .const import KYIV


@lru_cache(maxsize=32)
def daylight(day: date, latitude: float, longitude: float) -> list[dict] | None:
    """Return bands in minutes on the Kyiv wall-clock timeline."""
    if not (
        isfinite(latitude)
        and isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
        and (latitude or longitude)
    ):
        return None
    observer = Observer(latitude, longitude)
    try:
        times = [
            event(observer, date=day, tzinfo=KYIV)
            for event in (dawn, sunrise, sunset, dusk)
        ]
    except ValueError:
        return None

    def minute(moment: datetime) -> int:
        return (moment.date() - day).days * 1440 + moment.hour * 60 + moment.minute

    bounds = [0, *(max(0, min(1440, minute(moment))) for moment in times), 1440]
    if bounds != sorted(bounds):
        return None
    return [
        {"start": start, "end": end, "phase": phase}
        for start, end, phase in zip(
            bounds[:-1],
            bounds[1:],
            ("night", "twilight", "day", "twilight", "night"),
            strict=True,
        )
        if start < end
    ]
