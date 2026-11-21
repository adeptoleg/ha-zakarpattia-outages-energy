"""Per-entry name, location and notification options."""

import voluptuous as vol
from homeassistant.config_entries import OptionsFlow
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    BooleanSelector,
    LocationSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .features import (
    CONF_CHANGES,
    CONF_GRID_DOWN,
    CONF_GRID_UP,
    CONF_LABEL,
    CONF_LEAD,
    CONF_LOCATION,
    CONF_NOTIFY,
    LEAD_OPTIONS,
)


class OutageOptionsFlow(OptionsFlow):
    """Configure options without changing the queue or entity IDs."""

    async def async_step_init(self, user_input: dict | None = None):
        entry = self.hass.config_entries.async_get_entry(self.handler)
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        targets = {
            f"service:{service}": f"notify.{service}"
            for service in self.hass.services.async_services().get("notify", {})
            if service not in {"send_message", "persistent_notification"}
        }
        for entity in er.async_get(self.hass).entities.values():
            if entity.domain == "notify" and not entity.disabled:
                targets[f"entity:{entity.entity_id}"] = entity.name or entity.entity_id
        for state in self.hass.states.async_all("notify"):
            targets.setdefault(f"entity:{state.entity_id}", state.name)
        if target := entry.options.get(CONF_NOTIFY):
            targets.setdefault(target, target.partition(":")[2])
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Optional(CONF_LABEL): TextSelector(),
                        vol.Optional(CONF_LOCATION): LocationSelector(
                            {"radius": False}
                        ),
                        vol.Optional(CONF_NOTIFY): SelectSelector(
                            SelectSelectorConfig(
                                options=[
                                    SelectOptionDict(value=value, label=label)
                                    for value, label in sorted(
                                        targets.items(), key=lambda item: item[1]
                                    )
                                ]
                            )
                        ),
                        vol.Optional(CONF_LEAD): SelectSelector(
                            SelectSelectorConfig(
                                options=list(LEAD_OPTIONS), multiple=True
                            )
                        ),
                        vol.Optional(CONF_CHANGES, default=False): BooleanSelector(),
                        vol.Optional(CONF_GRID_DOWN, default=False): BooleanSelector(),
                        vol.Optional(CONF_GRID_UP, default=False): BooleanSelector(),
                    }
                ),
                entry.options,
            ),
        )
