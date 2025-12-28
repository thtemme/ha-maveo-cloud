from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from .const import DOMAIN, CONF_DEVICE_ID

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    bridge = hass.data[DOMAIN][entry.entry_id]
    device_id = entry.data[CONF_DEVICE_ID]
    async_add_entities([MaveoLight(bridge, device_id)])

class MaveoLight(SwitchEntity):
    def __init__(self, bridge, device_id):
        self._bridge = bridge
        self._attr_unique_id = f"{device_id}_light"
        self._attr_name = "Maveo Licht"
        self._attr_icon = "mdi:lightbulb"
        self._is_on = False

    async def async_added_to_hass(self):
        self._bridge.register_callback(self.update_status)

    @callback
    def update_status(self, payload):
        # Wir bräuchten vom Reverse Engineering noch den Status-Code für Licht (StoA_l ?)
        # Solange wir den nicht haben, arbeiten wir "optimistisch" (Button State ändert sich bei Klick)
        pass 

    @property
    def is_on(self):
        return self._is_on

    def turn_on(self, **kwargs):
        self._bridge.send_command({"AtoS_l": 1})
        self._is_on = True
        self.async_write_ha_state()

    def turn_off(self, **kwargs):
        self._bridge.send_command({"AtoS_l": 0})
        self._is_on = False
        self.async_write_ha_state()