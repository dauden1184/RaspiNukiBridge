import asyncio
import os

import yaml

from __main__ import config_file, _random_app_id_and_token, _generate_bridge_keys
from nuki import NukiManager, Nuki
from scan_ble import find_ble_device
from utils import logger


def init_config():
    config_updated = False
    if os.path.isfile(config_file):
        with open(config_file) as f:
            data = yaml.load(f, Loader=yaml.FullLoader)
    else:
        app_id, token = _random_app_id_and_token()
        data = {
            'server': {
                'host': '0.0.0.0',
                'port': '8080',
                'name': 'RaspiNukiBridge',
                'app_id': app_id,
                'token': token
            }
        }
    name = data["server"]["name"]
    app_id = data["server"]["app_id"]
    bt_adapter = data["server"].get("adapter", "hci0")
    nuki_manager = NukiManager(name, app_id, bt_adapter)
    if 'smartlock' not in data:
        bridge_public_key, bridge_private_key = _generate_bridge_keys()
        data['smartlock'] = {
            'bridge_public_key': bridge_public_key,
            'bridge_private_key': bridge_private_key
        }
        config_updated = True
    else:
        bridge_public_key = data['smartlock']['bridge_public_key']
        bridge_private_key = data['smartlock']['bridge_private_key']
    if 'address' not in data['smartlock']:
        data['smartlock']['address'] = find_ble_device('Nuki_.*', logger)
        config_updated = True
    if 'nuki_public_key' not in data['smartlock']:
        address = data['smartlock']['address']
        nuki = Nuki(address, None, None, bridge_public_key, bridge_private_key)

        def pairing_completed(paired_nuki):
            return paired_nuki.nuki_public_key.hex(), paired_nuki.auth_id.hex()

        loop = asyncio.get_event_loop()
        nuki_public_key, auth_id = loop.run_until_complete(nuki.pair(pairing_completed))
        loop.close()
        data['smartlock']['nuki_public_key'] = nuki_public_key
        data['smartlock']['auth_id'] = auth_id
        config_updated = True
    if config_updated:
        yaml.dump(data, open(config_file, 'w'))
    return nuki_manager, data
