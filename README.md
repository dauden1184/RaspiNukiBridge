Home Assistant Virtual Nuki Bridge
=
Run this on your Home Assistant instead of using [Nuki Bridge](https://nuki.io/en/bridge/).
> **WARNING** Work-in-progress. Unstable.

This project is a work-in-progress of running [dauden1184](https://github.com/dauden1184/) 's [RaspiNukiBridge](https://github.com/dauden1184/RaspiNukiBridge) as a Home Assistant Addon.

There's a similar effort [here](https://github.com/ftarolli/NukiBridgeAddon).
# Installation
## Install addon
### Install SSH
1. Enable advanced mode in your user profile
2. Go to the Add-on store

   [![Open your Home Assistant instance and show the Supervisor add-on store.](https://my.home-assistant.io/badges/supervisor_store.svg)](https://my.home-assistant.io/redirect/supervisor_store/)
4. Install one of the SSH add-ons
5. Configure the SSH add-on you chose by following the documentation for it
6. Start the SSH add-on

### Download addon locally
1. Connect to the SSH add-on

   `ssh root@homeassistant.local`
2. `cd addons`
3. `git clone https://github.com/f1ren/RaspiNukiBridge/`

### Install local addon
1. Go to Home Assistant -> Configuration -> Add-ons, backups & Supervisor -> add-on store (in the bottom right corner)

   [![Open your Home Assistant instance and show the Supervisor add-on store.](https://my.home-assistant.io/badges/supervisor_store.svg)](https://my.home-assistant.io/redirect/supervisor_store/)
3. On the top right overflow menu ⋮  click the "Check for updates" button
5. Install the addon. It takes a few minutes.
6. *Don't start it yet!*

## Pair with lock
1. Press the button of the Nuki Smart Lock for 6 seconds. It should light up.
2. Start the addon by clicking "start"
3. Look in logs for:

   ```
   ********************************************************************
   *                                                                  *
   *                         Pairing completed!                       *
   *                            Access Token                          *
   * abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca *
   *                                                                  *
   ********************************************************************
   ```
4. Copy the access token for a following step.

   In case you missed it, restart the service and check again.

## Nuki Addon
1. Restart the addon (first run is less stable)
2. Install either
   1. [Official Home Assistant Nuki integration](https://www.home-assistant.io/integrations/nuki/)
   2. [hass_nuki_ng](https://github.com/kvj/hass_nuki_ng)
3. Configure the Nuki Addon:
   1. Paste your token from the log above
   2. Address is `127.0.0.1`

# Enjoy!