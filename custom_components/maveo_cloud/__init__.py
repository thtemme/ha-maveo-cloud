import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, CONF_MAVEO_USER, CONF_MAVEO_PASS, CONF_DEVICE_ID
from .maveo_bridge import MaveoBridge

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["cover", "switch"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Maveo from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    user = entry.data[CONF_MAVEO_USER]
    password = entry.data[CONF_MAVEO_PASS]
    device_id = entry.data[CONF_DEVICE_ID]

    # Bridge Instanz erstellen
    bridge = MaveoBridge(user, password, device_id)
    
    # Bridge speichern, damit cover.py und switch.py sie finden
    hass.data[DOMAIN][entry.entry_id] = bridge
    
    # Bridge starten (im Thread)
    bridge.start()

    # Plattformen (Cover, Switch) laden
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # Bridge stoppen
    bridge = hass.data[DOMAIN][entry.entry_id]
    bridge.stop()
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok