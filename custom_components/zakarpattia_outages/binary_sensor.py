"""Expose actual grid power from a local Home Assistant binary sensor."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from . import ScheduleEntry
from .const import CONF_GRID_SENSOR, CONF_INVERT_GRID, CONF_QUEUE


async def async_setup_entry(
    hass: HomeAssistant, entry: ScheduleEntry, async_add_entities: AddEntitiesCallback
) -> None:
    if source := entry.data.get(CONF_GRID_SENSOR):
        async_add_entities(
            [
                GridPower(
                    entry.data[CONF_QUEUE],
                    source,
                    entry.data.get(CONF_INVERT_GRID, False),
                )
            ]
        )


class GridPower(BinarySensorEntity):
    """Map the configured sensor to on when grid power is present."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.POWER
    _attr_translation_key = "grid_power"

    def __init__(self, queue: str, source: str, inverted: bool) -> None:
        self._source = source
        self._inverted = inverted
        self._attr_unique_id = f"{queue}_grid_power"
        self._attr_translation_placeholders = {"queue": queue}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._source, self._async_grid_changed
            )
        )
        self._async_update_grid_state()

    @callback
    def _async_grid_changed(self, _event) -> None:
        self._async_update_grid_state()
        self.async_write_ha_state()

    @callback
    def _async_update_grid_state(self) -> None:
        source = self.hass.states.get(self._source)
        self._attr_available = source is not None and source.state in (
            STATE_ON,
            STATE_OFF,
        )
        self._attr_is_on = (
            (source.state == STATE_ON) != self._inverted
            if self._attr_available
            else None
        )
