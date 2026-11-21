"""Published schedule status and next known outage."""

from datetime import UTC, datetime
from typing import ClassVar

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ScheduleEntry
from .const import KYIV, SOURCE_URL
from .entity import ScheduleEntity
from .schedule import ONE_DAY


async def async_setup_entry(
    hass: HomeAssistant, entry: ScheduleEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [ScheduleStatus(coordinator, "status"), NextOutage(coordinator, "next_outage")]
    )


class ScheduleStatus(ScheduleEntity, SensorEntity):
    """Show what the published hourly schedule says about the current time."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = [
        "unpublished",
        "outage_scheduled",
        "no_outage_scheduled",
    ]

    @property
    def native_value(self) -> str:
        now = datetime.now(UTC)
        _, intervals = next(self.published_days(now))
        if intervals is None:
            return "unpublished"
        if any(interval.start <= now < interval.end for interval in intervals):
            return "outage_scheduled"
        return "no_outage_scheduled"

    @property
    def extra_state_attributes(self) -> dict:
        now = datetime.now(UTC)
        today = now.astimezone(KYIV).date()
        published = (self.coordinator.data or {}) if self.available else {}
        return {
            "all_queues": {
                day.isoformat(): published.get(day, {})
                for day in (today, today + ONE_DAY)
            },
            "queue": self.coordinator.queue,
            "source": SOURCE_URL,
            "schedule": {
                day.isoformat(): (
                    None
                    if intervals is None or not self.available
                    else [
                        {
                            "start": interval.start.astimezone(KYIV).isoformat(),
                            "end": interval.end.astimezone(KYIV).isoformat(),
                        }
                        for interval in intervals
                    ]
                )
                for day, intervals in self.published_days(now)
            },
        }


class NextOutage(ScheduleEntity, SensorEntity):
    """Expose the next published start time for dashboard and automations."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        now = datetime.now(UTC)
        return next(
            (
                interval.start
                for interval in self.current_intervals(now)
                if now < interval.start
            ),
            None,
        )
