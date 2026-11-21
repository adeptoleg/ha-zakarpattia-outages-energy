"""Choose a Zakarpattia subqueue and optionally link a grid sensor."""

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_GRID_SENSOR, CONF_INVERT_GRID, CONF_QUEUE, DOMAIN, QUEUES

_GRID_FIELDS = {
    vol.Optional(CONF_GRID_SENSOR): EntitySelector(
        EntitySelectorConfig(filter={"domain": "binary_sensor"})
    ),
    vol.Optional(CONF_INVERT_GRID, default=False): BooleanSelector(),
}


class OutageConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create one config entry per subqueue."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        if user_input is not None:
            queue = user_input[CONF_QUEUE]
            await self.async_set_unique_id(queue)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=f"ГПВ {queue}", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_QUEUE): SelectSelector(
                        SelectSelectorConfig(options=list(QUEUES))
                    ),
                    **_GRID_FIELDS,
                }
            ),
        )

    async def async_step_reconfigure(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry, data={CONF_QUEUE: entry.data[CONF_QUEUE], **user_input}
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(_GRID_FIELDS), entry.data
            ),
        )
