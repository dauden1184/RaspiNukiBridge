# RaspiNukiBridge
Simple [Nuki Bridge](https://nuki.io/en/bridge/) implementation using asyncio.

Minimal implementation of the Nuki Bridge protocols in python (both HTTP and BLE), I use it on a raspberry pi zero W and a Nuki smartlock V2.  
Right now **pairing**, **lock**, **unlock**, **unlatch** and HTTP callbacks are implemented, it works fine with the [Homeassistant Nuki integration](https://www.home-assistant.io/integrations/nuki/) and the [hass_nuki_ng integration](https://github.com/kvj/hass_nuki_ng).

Nuki documentation:  
https://developer.nuki.io/page/nuki-smart-lock-api-2/2/#heading--lock-action  
https://developer.nuki.io/page/nuki-bridge-http-api-1-13/4/#heading--lockstate  
  
This is heavily inspired by the work of [Jandebeule](https://github.com/jandebeule/nukiPyBridge).
  
# Installation

> ### Raspberry Pi 3B+ and 4 only
> DOWNGRADE Bluez. [See comment](https://github.com/dauden1184/RaspiNukiBridge/issues/1#issuecomment-1103969957).
> ```
> wget http://ftp.hk.debian.org/debian/pool/main/b/bluez/bluez_5.50-1.2~deb10u2_armhf.deb
> sudo apt install ./bluez_5.50-1.2~deb10u2_armhf.deb
> ```
> Reboot the Raspberry Pi

Clone the repository.
```
git clone https://github.com/dauden1184/RaspiNukiBridge.git
```

Install the requirements.
```
pip install -r requirements.txt
```

Generate a new configuration file.
```
python . --generate-config > nuki.yaml
```

This will generate a nuki.yaml file similar to this:
```
server:
  host: 0.0.0.0
  port: 8080
  name: RaspiNukiBridge
  app_id: xxxxxxxxx
  token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
**app_id** and **token** are generate randomly.  
**app_id** is needed to communicate with the smartlock over bluetooth.  
**token** is the api token used for the HTTP calls (this is needed when configuring the homeassistant nuki integration).  
  

Pair the smartlock (this must be done only once).  
You need to find the MAC address of your nuki smartlock, you can use a BLE scanner app.  
Press for 6 seconds the button on the nuki to set it in pairing mode (the ring will turn on).  
After that:
```
python . --pair MAC_ADDRESS
```

Sometimes the bluetooth connection fails, try a few times if it happens.  
If the pairing procedure is successfull, you will find these lines on the screen:
```
INFO:root:Generatig keys for Nuki XX:XX:XX:XX:XX:XX
INFO:root:bridge_public_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
INFO:root:bridge_private_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
.
. other stuff
.
INFO:root:Pairing completed, nuki_public_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
INFO:root:Pairing completed, auth_id: xxxxxxxx
```

You can now edit the nuki.yaml file created before and add those lines like this at the end of the file:
```
smartlock:
  - address: XX:XX:XX:XX:XX:XX
    bridge_public_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    bridge_private_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    nuki_public_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    auth_id: xxxxxxxx
```

# Usage

## Test manually
```
python .  --lock
python .  --unlock
```

## Bridge server for HA
Save the file and start the bridge:
```
python .
```
Install either:
1. [hass_nuki_ng integration](https://github.com/kvj/hass_nuki_ng)
2. [Homeassistant Nuki integration](https://www.home-assistant.io/integrations/nuki/)
# Advanced
## Connection timeout and retries

In case of issues during the bluetooth connection to the nuki device, it is possible to set a higher connection timeout and the number of retries with the fields `connection_timeout` (default is 10 seconds) and `retry` (default is 3) like this:

```
smartlock:
  - address: XX:XX:XX:XX:XX:XX
    bridge_public_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    bridge_private_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    nuki_public_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    auth_id: xxxxxxxx
    connection_timeout: 30
    retry: 5
```

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
