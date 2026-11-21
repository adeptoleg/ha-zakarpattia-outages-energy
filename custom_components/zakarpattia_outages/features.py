"""Local notification delivery and history of measured grid outages."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from math import ceil
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import (
    CONF_GRID_SENSOR,
    CONF_INVERT_GRID,
    DOMAIN,
    EVENT_SCHEDULE_CHANGED,
    KYIV,
)

CONF_LABEL = "location_label"
CONF_LOCATION = "schedule_location"
CONF_NOTIFY = "notify_target"
CONF_LEAD = "notify_lead"
CONF_CHANGES = "notify_changes"
CONF_GRID_DOWN = "notify_grid_down"
CONF_GRID_UP = "notify_grid_up"
LEAD_OPTIONS = ("15", "30", "60")
MAX_HISTORY = 60
MAX_SENT = 96
_LOGGER = logging.getLogger(__name__)

_TEXT = {
    "uk": {
        "advance": "Відключення за графіком о {time}. Залишилося {minutes} хв.",
        "changes": "Оператор опублікував зміни графіка: {dates}.",
        "down": "Датчик зафіксував зникнення мережі.",
        "up": "Датчик зафіксував відновлення мережі.",
    },
    "en": {
        "advance": "Scheduled outage at {time}, in {minutes} min.",
        "changes": "The operator changed the schedule: {dates}.",
        "down": "The sensor detected a grid outage.",
        "up": "The sensor detected that grid power was restored.",
    },
}


def feature_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    return Store(hass, 1, f"{DOMAIN}.{entry_id}.features")


class EntryFeatures:
    """Keep one independent set of settings and measured events per entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        queue: str,
        title: str,
        operator_id: str | None = None,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.options = dict(entry.options)
        self._grid_identity = [
            entry.data.get(CONF_GRID_SENSOR),
            bool(entry.data.get(CONF_INVERT_GRID)),
        ]
        self.label = self.options.get(CONF_LABEL)
        self.queue = queue
        self.title = self.options.get(CONF_LABEL) or title
        self.operator_id = operator_id
        self.location = self.options.get(CONF_LOCATION)
        self.target = self.options.get(CONF_NOTIFY)
        self.lead = sorted(int(value) for value in self.options.get(CONF_LEAD, ()))
        self.store = feature_store(hass, entry.entry_id)
        self.history: list[dict] = []
        self.sent: list[str] = []
        self.plan: Callable = lambda now: ()
        self._start: datetime | None = None
        self._start_plan: tuple = ()
        self._pending: set[str] = set()
        self._dirty = False

    async def async_start(self) -> None:
        if not (self.target or self._grid_identity[0]):
            return
        saved = await self.store.async_load() or {}
        self.history = saved.get("history", [])[-MAX_HISTORY:]
        self.sent = saved.get("sent", [])[-MAX_SENT:]
        # A different source (or inversion) defines a new measurement series.
        if saved.get("grid") != self._grid_identity:
            self.history = []
        if self.target and self.options.get(CONF_CHANGES):
            self.entry.async_on_unload(
                self.hass.bus.async_listen(
                    EVENT_SCHEDULE_CHANGED, self._on_schedule_change
                )
            )

    def _snapshot(self) -> dict:
        return {"grid": self._grid_identity, "history": self.history, "sent": self.sent}

    @callback
    def _persist(self) -> None:
        self._dirty = True
        self.store.async_delay_save(self._snapshot, 5)

    async def async_flush(self) -> None:
        if self._dirty:
            await self.store.async_save(self._snapshot())

    @callback
    def _on_schedule_change(self, event: Event) -> None:
        if (
            event.data.get("queue") != self.queue
            or event.data.get("operator") != self.operator_id
        ):
            return
        self._send("changes", dates=", ".join(event.data.get("dates", ())))

    @callback
    def async_check_advance(self, now: datetime) -> None:
        if not self.target or not self.lead:
            return
        span = next((item for item in self.plan(now) if item.start > now), None)
        if span is None:
            return
        seconds = (span.start - now).total_seconds()
        keys = tuple(
            f"{span.start.isoformat()}:{lead}"
            for lead in self.lead
            if seconds <= lead * 60
        )
        if not keys or keys[0] in self.sent or keys[0] in self._pending:
            return
        self._send(
            "advance",
            keys,
            time=span.start.astimezone(KYIV).strftime("%H:%M"),
            minutes=ceil(seconds / 60),
        )

    @callback
    def async_grid_changed(
        self, previous: bool | None, current: bool | None, now: datetime
    ) -> None:
        if current is previous:
            return
        if current is None or previous is None:
            # Duration across an unobserved change cannot be measured reliably.
            self._start, self._start_plan = None, ()
            return

        now = now.astimezone(UTC)
        if not current:
            self._start, self._start_plan = now, self.plan(now)
            if self.options.get(CONF_GRID_DOWN):
                self._send("down")
            return

        if (start := self._start) is not None:
            plans = (*self._start_plan, *self.plan(now))
            overlap = lambda span: min(now, span.end) - max(start, span.start)
            match = max(
                (span for span in plans if span.start < now and start < span.end),
                key=overlap,
                default=None,
            )
            self.history = [
                *self.history[-(MAX_HISTORY - 1) :],
                {
                    "start": start.isoformat(),
                    "end": now.isoformat(),
                    "planned_start": match.start.isoformat() if match else None,
                    "planned_end": match.end.isoformat() if match else None,
                },
            ]
            self._persist()
        self._start, self._start_plan = None, ()
        if self.options.get(CONF_GRID_UP):
            self._send("up")

    @callback
    def _send(self, kind: str, keys: tuple[str, ...] = (), **details) -> None:
        if not self.target:
            return
        self._pending.update(keys)
        self.entry.async_create_background_task(
            self.hass, self._deliver(kind, keys, details), f"{DOMAIN} notification"
        )

    async def _deliver(self, kind: str, keys: tuple[str, ...], details: dict) -> None:
        language = "uk" if self.hass.config.language.startswith("uk") else "en"
        data = {"message": _TEXT[language][kind].format(**details), "title": self.title}
        try:
            if self.target.startswith("entity:"):
                await self.hass.services.async_call(
                    "notify",
                    "send_message",
                    {"message": f"{self.title} · {data['message']}"},
                    target={"entity_id": self.target.removeprefix("entity:")},
                    blocking=True,
                )
            else:
                service = self.target.removeprefix("service:")
                await self.hass.services.async_call(
                    "notify", service, data, blocking=True
                )
        except Exception:
            _LOGGER.warning(
                "Could not deliver %s notification for %s",
                kind,
                self.entry.entry_id,
                exc_info=True,
            )
        else:
            if keys:
                self.sent = list(dict.fromkeys([*self.sent, *keys]))[-MAX_SENT:]
                self._persist()
        finally:
            self._pending.difference_update(keys)
