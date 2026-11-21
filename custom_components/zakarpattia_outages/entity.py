"""Common schedule entity behaviour."""

from collections.abc import Iterator
from datetime import date, datetime, time

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ScheduleCoordinator
from .const import KYIV
from .schedule import ONE_DAY, Outage, day_intervals, merge_intervals


class ScheduleEntity(CoordinatorEntity[ScheduleCoordinator]):
    """Refresh the state at minute boundaries between source polls."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ScheduleCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.queue}_{key}"
        self._attr_translation_key = key
        self._attr_translation_placeholders = {"queue": coordinator.queue}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_utc_time_change(self.hass, self._async_tick, second=0)
        )

    @callback
    def _async_tick(self, _now: datetime) -> None:
        self.async_write_ha_state()

    def published_days(
        self, now: datetime
    ) -> Iterator[tuple[date, tuple[Outage, ...] | None]]:
        """Include the local day and the next day, even if unpublished."""
        today = now.astimezone(KYIV).date()
        for day in (today, today + ONE_DAY):
            slots = (
                (self.coordinator.data or {}).get(day, {}).get(self.coordinator.queue)
            )
            yield day, day_intervals(day, slots) if slots is not None else None

    def current_intervals(self, now: datetime) -> tuple[Outage, ...]:
        """Return all known intervals in the current schedule horizon."""
        if not self.available:
            return ()
        return merge_intervals(
            interval
            for _, day_intervals in self.published_days(now)
            if day_intervals is not None
            for interval in day_intervals
        )

    def scheduled_outage(self, now: datetime) -> datetime | None:
        """Find the first future published outage start."""
        return next(
            (
                interval.start
                for interval in self.current_intervals(now)
                if now < interval.start
            ),
            None,
        )

    def scheduled_restoration(self, now: datetime) -> datetime | None:
        """Find the first known outage end, excluding an unpublished midnight boundary."""
        for interval in self.current_intervals(now):
            if now >= interval.end:
                continue
            end = interval.end.astimezone(KYIV)
            if end.time() == time.min:
                slots = (self.coordinator.data or {}).get(end.date(), {})
                if self.coordinator.queue not in slots:
                    return None
            return interval.end
        return None
