"""Home Assistant integration for Zakarpattia hourly outage schedules."""

import json
import logging
from datetime import datetime
from pathlib import Path

import aiohttp
from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CARD_URL,
    CONF_QUEUE,
    DOMAIN,
    EVENT_SCHEDULE_CHANGED,
    KYIV,
    PANEL_PATH,
    SOURCE_URL,
    UPDATE_INTERVAL,
)
from .schedule import ONE_DAY, PublishedSchedules, parse_schedule

_LOGGER = logging.getLogger(__name__)
_PLATFORMS = (Platform.CALENDAR, Platform.SENSOR, Platform.BINARY_SENSOR)
_MAX_RESPONSE = 512 * 1024


class ScheduleCoordinator(DataUpdateCoordinator[PublishedSchedules]):
    """Fetch the regional schedule and announce revisions to the selected queue."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self.queue: str = entry.data[CONF_QUEUE]
        self.session = async_get_clientsession(hass)

    async def _async_update_data(self) -> PublishedSchedules:
        try:
            async with self.session.get(
                SOURCE_URL,
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise UpdateFailed(f"Schedule feed returned HTTP {response.status}")
                body = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    body.extend(chunk)
                    if len(body) > _MAX_RESPONSE:
                        raise UpdateFailed("Schedule feed response is too large")
            today = datetime.now(KYIV).date()
            schedules = parse_schedule(json.loads(body), today)
        except (
            aiohttp.ClientError,
            TimeoutError,
            ValueError,
            TypeError,
            OSError,
            OverflowError,
        ) as err:
            raise UpdateFailed(
                f"Unable to read the outage schedule: {err or type(err).__name__}"
            ) from err

        if self.data is not None:
            changed = [
                day.isoformat()
                for day in (today, today + ONE_DAY)
                if self.data.get(day, {}).get(self.queue)
                != schedules.get(day, {}).get(self.queue)
            ]
            if changed:
                self.hass.bus.async_fire(
                    EVENT_SCHEDULE_CHANGED, {"queue": self.queue, "dates": changed}
                )
        return schedules


type ScheduleEntry = ConfigEntry[ScheduleCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Make the dashboard card available to Home Assistant."""
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                CARD_URL, str(Path(__file__).with_name("schedule-card.js")), False
            )
        ]
    )
    frontend.add_extra_js_url(hass, CARD_URL)
    hass.data[DOMAIN] = set()
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ScheduleEntry) -> bool:
    """Set up the selected subqueue and optional grid measurement."""
    coordinator = ScheduleCoordinator(hass, entry)
    await coordinator.async_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    active_entries = hass.data[DOMAIN]
    if not active_entries:
        await async_register_panel(
            hass,
            frontend_url_path=PANEL_PATH,
            webcomponent_name="zakarpattia-outages-panel",
            sidebar_title="Графік світла",
            sidebar_icon="mdi:transmission-tower",
            module_url=CARD_URL,
            trust_external=True,
        )
    active_entries.add(entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ScheduleEntry) -> bool:
    """Unload the integration's entities."""
    if not await hass.config_entries.async_unload_platforms(entry, _PLATFORMS):
        return False
    active_entries = hass.data[DOMAIN]
    active_entries.discard(entry.entry_id)
    if not active_entries:
        frontend.async_remove_panel(hass, PANEL_PATH)
    return True
