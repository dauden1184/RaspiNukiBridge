Home Assistant Virtual Nuki Bridge
=
Use this instead of the [Nuki Bridge](https://nuki.io/en/bridge/) device.

## Background
* This is heavily inspired by the work of [Jandebeule](https://github.com/jandebeule/nukiPyBridge).
* Forked from [dauden1184](https://github.com/dauden1184/) 's [RaspiNukiBridge](https://github.com/dauden1184/RaspiNukiBridge)
* Similar project [here](https://github.com/ftarolli/NukiBridgeAddon)
* Nuki documentation
  * [Nuki Smart Lock API V2.2.1](https://developer.nuki.io/page/nuki-smart-lock-api-2/2/#heading--lock-action)
  * [Nuki Bridge HTTP API V1.13.1](https://developer.nuki.io/page/nuki-bridge-http-api-1-13/4/#heading--lockstate)

# Installation
There are 2 methods:
1. [As a Home Assistant Addon](#installation-as-home-assistant-addon)
   1. Use this if your Home Assistant is nearby the Nuki Smart Lock
2. [Outside of Home Assistant](#installation-outside-of-home-assistant-os)
   1. Use this if your Home Assistant too far from the Nuki Smart Lock

# Installation outside of Home Assistant OS
## Get the files
> ### Raspberry Pi 3B+ and 4 only
> DOWNGRADE Bluez. [See comment](https://github.com/dauden1184/RaspiNukiBridge/issues/1#issuecomment-1103969957).
> ```
> wget http://ftp.hk.debian.org/debian/pool/main/b/bluez/bluez_5.50-1.2~deb10u2_armhf.deb
> sudo apt install ./bluez_5.50-1.2~deb10u2_armhf.deb
> ```
> Reboot the Raspberry Pi

1. Clone the repository.

   ```
   git clone https://github.com/f1ren/RaspiNukiBridge.git
   ```

2. Install the requirements.

   ```
   pip install -r requirements.txt
   ```
3. Go to [pairing](#pairing)

## Start automatically at boot

Create a new systemd service:

```
sudo nano /etc/systemd/system/nukibridge.service
```

Put this content in the file (change 'user' and 'WorkingDirectory' to your needs):

```
[Unit]
Description=Nuki bridge
After=network-online.target
[Service]
Type=simple
Restart=always
RestartSec=1
User=pi
WorkingDirectory=/home/pi/RaspiNukiBridge/
ExecStart=python .
[Install]
WantedBy=multi-user.target
```

Enable the service and start it:

```
sudo systemctl daemon-reload
sudo systemctl enable nukibridge.service
sudo systemctl start nukibridge.service
```

# Installation as Home Assistant Addon
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

# Pairing
1. Press the button of the Nuki Smart Lock for 6 seconds. It should light up.
2. Run
   1. If installed as addon, click `start`
   2. If installed outside HA, run
   
      ```python .```
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
4. Copy the `Access Token` for a following step.

   In case you missed it, restart the service and check again.
5. Before moving on, you might need to restart the addon. First run is less stable.

# Nuki Addon
1. Install either
   1. [Official Home Assistant Nuki integration](https://www.home-assistant.io/integrations/nuki/)
   2. [hass_nuki_ng](https://github.com/kvj/hass_nuki_ng)
2. Configure the Nuki Addon:
   1. Paste your token from the log above
   2. Address is `127.0.0.1`

# Enjoy!
