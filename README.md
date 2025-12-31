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
9. You get two new entities: "Maveo garagedoor" and "Maveo Light"

# Disclaimer
This integration is unofficial, so always use it at your own risk. No guarantee for anything. It might stop working at any time in the future, if Maveo changes something.
As this integration is quite new, let me know if you observe any issues.
