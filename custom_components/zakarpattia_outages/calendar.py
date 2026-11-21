"""Calendar of published outage intervals."""

from datetime import UTC, datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ScheduleEntry
from .entity import ScheduleEntity
from .schedule import Outage


async def async_setup_entry(
    hass: HomeAssistant, entry: ScheduleEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([OutageCalendar(entry.runtime_data, "schedule")])


class OutageCalendar(ScheduleEntity, CalendarEntity):
    """Expose the current and upcoming published outages."""

    def _event(self, outage: Outage) -> CalendarEvent:
        queue = self.coordinator.queue
        return CalendarEvent(
            start=outage.start,
            end=outage.end,
            summary=f"ГПВ {queue} · Відключення за графіком",
            uid=f"zakarpattia-{queue}-{outage.start.isoformat()}",
        )

    @property
    def event(self) -> CalendarEvent | None:
        now = datetime.now(UTC)
        return next(
            (
                self._event(interval)
                for interval in self.current_intervals(now)
                if now < interval.end
            ),
            None,
        )

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        start = start_date.astimezone(UTC)
        end = end_date.astimezone(UTC)
        return [
            self._event(interval)
            for interval in self.current_intervals(datetime.now(UTC))
            if interval.start < end and start < interval.end
        ]
