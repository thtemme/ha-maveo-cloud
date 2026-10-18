# Maveo Garage Door cloud integration (unofficial)
Maveo garage door integration via Maveo Cloud (unofficial).
This Addon allows you to control your Maveo Garage door via the Maveo stick. As for newer Maveo sticks the local access via TCP or UDP is blocked, this integration controls the garage door via the Maveo cloud.

If you have the possibility to get local access to your Maveo stick via TCP or UDP (blocked for newer Maveo Sticks), use this integration instead:
https://github.com/Mattes83/nymea

# Installation

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner and select "Custom repositories"
3. Add this repository URL: https://github.com/thtemme/ha-maveo-cloud
4. Select "Integration" as the category
5. Click "Add"
6. Enter your Username and password of your Maveo account
7. Open the Maveo App, go to Settings and Search for the serial number of your stick
8. Enter the Serial Number as DeviceId in the Integration
9. You get three new entities: the garage door cover "Maveo Garagentor", the light switch "Maveo Licht" and the door status sensor "Maveo Torstatus"

# Door status and ventilation position
Home Assistant covers only know the states open, closed, opening and closing. The Maveo stick reports more than that, so the integration exposes the detailed status in three ways:

| Stick status | Cover state | Tilt position | Door status (sensor and cover attribute `door_status`) |
|---|---|---|---|
| Fully closed | closed | 0 | closed |
| Fully open | open | 0 | open |
| Opening / closing | opening / closing | 0 | opening / closing |
| Stopped between the end positions | open | 0 | stopped |
| Ventilation position | open | 100 | ventilation |

- The ventilation position is triggered with "open tilt" (`cover.open_cover_tilt`) and reported back as tilt position 100, so automations can check `current_tilt_position`.
- While the door is stopped or in the ventilation position, open and close stay enabled in the dashboard.
- The more-info dialog of the cover always shows the cover state, i.e. "Open" in the ventilation position. The detailed status is shown by the sensor and by the tile card below.

# Dashboard card
A tile card can show the detailed status (e.g. "Ventilation") together with the controls. Adjust the entity ID if yours differs:

```yaml
type: tile
entity: cover.maveo_garagentor
name: Garage door
state_content: door_status
features:
  - type: cover-open-close
  - type: cover-tilt
```

`cover-open-close` shows open, stop and close, `cover-tilt` adds the button for the ventilation position.

# Disclaimer
This integration is unofficial, so always use it at your own risk. No guarantee for anything. It might stop working at any time in the future, if Maveo changes something.
As this integration is quite new, let me know if you observe any issues.
