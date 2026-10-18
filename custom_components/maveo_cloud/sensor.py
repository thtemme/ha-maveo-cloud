import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from .const import DOMAIN, CONF_DEVICE_ID, STATUS_MAP

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    bridge = hass.data[DOMAIN][entry.entry_id]
    device_id = entry.data[CONF_DEVICE_ID]
    async_add_entities([MaveoDoorStatus(bridge, device_id)])

class MaveoDoorStatus(SensorEntity):
    """Detaillierter Torstatus inkl. Lüftungsposition und Stopp."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(STATUS_MAP.values())
    _attr_translation_key = "door_status"
    _attr_icon = "mdi:garage-variant"

    def __init__(self, bridge, device_id):
        self._bridge = bridge
        self._attr_unique_id = f"{device_id}_door_status"
        self._attr_name = "Maveo Torstatus"
        self._attr_native_value = None

    async def async_added_to_hass(self):
        unregister = self._bridge.register_callback(self.update_status)
        if callable(unregister):
            self.async_on_remove(unregister)

    @callback
    def update_status(self, payload):
        """Callback von der Bridge."""
        if "StoA_s" in payload:
            status = payload["StoA_s"]
            self._attr_native_value = STATUS_MAP.get(status)
            if self._attr_native_value is None:
                _LOGGER.debug("Unbekannter Torstatus von Maveo: %s", payload)
            self.schedule_update_ha_state()
