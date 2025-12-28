import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN, CONF_MAVEO_USER, CONF_MAVEO_PASS, CONF_DEVICE_ID

class MaveoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Maveo Cloud."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Hier könnte man theoretisch testen, ob Login klappt
            # Wir speichern einfach direkt für den Moment
            await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Maveo Garage ({user_input[CONF_DEVICE_ID]})", 
                data=user_input
            )

        data_schema = vol.Schema({
            vol.Required(CONF_MAVEO_USER): str,
            vol.Required(CONF_MAVEO_PASS): str,
            vol.Required(CONF_DEVICE_ID): str,
        })

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )