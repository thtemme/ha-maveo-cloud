import logging

from homeassistant.components.cover import CoverEntity, CoverDeviceClass, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_CLOSED, STATE_OPEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.restore_state import RestoreEntity
from .const import DOMAIN, CONF_DEVICE_ID

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    bridge = hass.data[DOMAIN][entry.entry_id]
    device_id = entry.data[CONF_DEVICE_ID]
    async_add_entities([MaveoGarage(bridge, device_id)])

class MaveoGarage(CoverEntity, RestoreEntity):
    def __init__(self, bridge, device_id):
        self._bridge = bridge
        self._attr_unique_id = f"{device_id}_garage"
        self._attr_name = "Maveo Garagentor"
        self._attr_device_class = CoverDeviceClass.GARAGE
        
        # Startzustand: None = Unbekannt -> Beide Buttons aktiv
        self._attr_is_closed = None
        self._attr_is_opening = False
        self._attr_is_closing = False
        # Tilt bildet die Lüftungsposition ab: 100 = Lüftung, 0 = keine Lüftung
        self._attr_current_cover_tilt_position = None

        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP | CoverEntityFeature.OPEN_TILT #für untere zwsichenposition
        )

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        # Letzten Zustand vor dem Neustart wiederherstellen, bis die Cloud antwortet.
        # Fahrzustände (opening/closing) werden nicht übernommen, die sind nach
        # einem Neustart nicht mehr aussagekräftig.
        last_state = await self.async_get_last_state()
        if last_state is not None:
            if last_state.state == STATE_CLOSED:
                self._attr_is_closed = True
            elif last_state.state == STATE_OPEN:
                self._attr_is_closed = False

        # Registrierung liefert sofort den zuletzt von der Cloud gemeldeten Status,
        # falls die Bridge schon vor dem Laden der Entity verbunden war.
        self.async_on_remove(self._bridge.register_callback(self.update_status))

        # Aktuellen Status zusätzlich aktiv anfragen
        await self.hass.async_add_executor_job(self._bridge.request_status)

    @callback
    def update_status(self, payload):
        """Callback von der Bridge."""
        if "StoA_s" in payload:
            status = payload["StoA_s"]
            _LOGGER.debug("Status von Maveo: %s", payload)
            
            # Reset erst mal alles
            self._attr_is_opening = False
            self._attr_is_closing = False
            # Standard: Tor steht zwischen den Endlagen (gestoppt, Zwischenposition).
            # Für Home Assistant ist ein nicht ganz geschlossenes Tor "offen".
            self._attr_is_closed = False

            # Status Mapping
            # 1: opening -> Wird geöffnet
            # 2: closing -> Wird geschlossen
            # 3: open    -> Ganz offen
            # 4: closed  -> Ganz zu
            # 0: gestoppt zwischen den Endlagen -> offen
            # 6: Lüftungsposition (untere Zwischenposition) -> offen
            
            if status == 3: 
                # Ganz offen -> Open Button grau, Close Button aktiv
                self._attr_is_closed = False
            
            elif status == 4: 
                # Ganz zu -> Open Button aktiv, Close Button grau
                self._attr_is_closed = True
            
            elif status == 1: 
                # Fährt auf -> Stop aktiv
                self._attr_is_opening = True
                self._attr_is_closed = False 
            
            elif status == 2: 
                # Fährt zu -> Stop aktiv
                self._attr_is_closing = True
                self._attr_is_closed = False
            
            # Alle anderen Werte (0, 6 und unbekannte) bleiben auf "offen".

            self._attr_current_cover_tilt_position = 100 if status == 6 else 0

            # Zwischen den Endlagen ist die genaue Position nicht bekannt. assumed_state
            # sorgt dafür, dass das Frontend Öffnen und Schließen aktiv lässt.
            self._attr_assumed_state = status not in (1, 2, 3, 4)

            # WICHTIG: schedule_update_ha_state nutzen statt async_write_ha_state
            self.schedule_update_ha_state()

    def open_cover(self, **kwargs):
        self._bridge.send_command({"AtoS_g": 1})

    def close_cover(self, **kwargs):
        self._bridge.send_command({"AtoS_g": 2})

    def stop_cover(self, **kwargs):
        self._bridge.send_command({"AtoS_g": 0})
        
    # Fahre in untere Zwischenposition
    def open_cover_tilt(self, **kwargs):
        self._bridge.send_command({"AtoS_g": 3})
