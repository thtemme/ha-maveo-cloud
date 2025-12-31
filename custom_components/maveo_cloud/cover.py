from homeassistant.components.cover import CoverEntity, CoverDeviceClass, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from .const import DOMAIN, CONF_DEVICE_ID

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    bridge = hass.data[DOMAIN][entry.entry_id]
    device_id = entry.data[CONF_DEVICE_ID]
    async_add_entities([MaveoGarage(bridge, device_id)])

class MaveoGarage(CoverEntity):
    def __init__(self, bridge, device_id):
        self._bridge = bridge
        self._attr_unique_id = f"{device_id}_garage"
        self._attr_name = "Maveo Garagentor"
        self._attr_device_class = CoverDeviceClass.GARAGE
        
        # --- DIESE ZEILEN FEHLTEN ---
        self._attr_is_closed = None  # Startzustand unbekannt
        self._attr_is_opening = False
        self._attr_is_closing = False
        # ----------------------------

        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )

    async def async_added_to_hass(self):
        """Wird aufgerufen, wenn Entität zu HA hinzugefügt wird."""
        self._bridge.register_callback(self.update_status)

    @callback
    def update_status(self, payload):
        """Callback von der Bridge."""
        if "StoA_s" in payload:
            status = payload["StoA_s"]
            # 1: opening, 2: closing, 3: open, 4: closed
            if status == 3: self._attr_is_closed = False; self._attr_is_closing = False; self._attr_is_opening = False
            elif status == 4: self._attr_is_closed = True; self._attr_is_closing = False; self._attr_is_opening = False
            elif status == 1: self._attr_is_opening = True; self._attr_is_closing = False; self._attr_is_closed = False
            elif status == 2: self._attr_is_closing = True; self._attr_is_opening = False; self._attr_is_closed = False
            
            self.async_write_ha_state()

    def open_cover(self, **kwargs):
        self._bridge.send_command({"AtoS_g": 1})

    def close_cover(self, **kwargs):
        self._bridge.send_command({"AtoS_g": 2})

    def stop_cover(self, **kwargs):
        # Hier ist dein gewünschter Stop-Code 0

        self._bridge.send_command({"AtoS_g": 0})
