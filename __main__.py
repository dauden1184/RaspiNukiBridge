import asyncio
import logging
import argparse

from config import init_config, _random_app_id_and_token, _generate_bridge_keys, get_config_file
from nuki import Nuki
from scan_ble import find_ble_device
from utils import logger, handler
from web_server import WebServer

logging.getLogger("aiohttp").addHandler(handler)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("bleak").addHandler(handler)
logging.getLogger("bleak").setLevel(logging.ERROR)

def _add_devices_to_manager(data, nuki_manager):
    for ls in data["smartlock"]:
        address = ls["address"]
        auth_id = bytes.fromhex(ls["auth_id"])
        nuki_public_key = bytes.fromhex(ls["nuki_public_key"])
        bridge_public_key = bytes.fromhex(ls["bridge_public_key"])
        bridge_private_key = bytes.fromhex(ls["bridge_private_key"])
        n = Nuki(address, auth_id, nuki_public_key, bridge_public_key, bridge_private_key)
        n.retry = ls.get("retry", 3)
        n.connection_timeout = ls.get("connection_timeout", 10)
        n.command_timeout = ls.get("command_timeout", 30)
        nuki_manager.add_nuki(n)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", metavar=('CONFIG_FILE',), help="Specify the yaml file to use")
    parser.add_argument("--pair", action='store_true', help="Pair to a nuki smartlock")
    parser.add_argument("--address", metavar=('MAC_ADDRESS',), help="Adresss of nuki smartlock to pair to")
    parser.add_argument("--generate-config", action='store_true', help="Generate a new configuration file")
    parser.add_argument("--unlock", action='store_true', help="Unlock")
    parser.add_argument("--lock", action='store_true', help="Lock")
    parser.add_argument("--verbose", nargs='?', const=1, type=int, default=0, help="More logs")
    args = parser.parse_args()

    if not args.verbose:
        logger.setLevel(level=logging.INFO)
        logging.getLogger("aiohttp").setLevel(level=logging.ERROR)
        logging.getLogger("bleak").setLevel(level=logging.ERROR)
    elif args.verbose == 1:
        logger.setLevel(level=logging.DEBUG)
        logging.getLogger("aiohttp").setLevel(level=logging.INFO)
        logging.getLogger("bleak").setLevel(level=logging.INFO)
    elif args.verbose == 2:
        logger.setLevel(level=logging.DEBUG)
        logging.getLogger("aiohttp").setLevel(level=logging.DEBUG)
        logging.getLogger("bleak").setLevel(level=logging.DEBUG)

    if args.generate_config:
        app_id, token = _random_app_id_and_token()
        print(f"server:\n"
              f"  host: 0.0.0.0\n"
              f"  port: 8080\n"
              f"  name: RaspiNukiBridge\n"
              f"  app_id: {app_id}\n"
              f"  token: {token}\n")
        exit(0)

    config_file = args.config or 'nuki.yaml'
    nuki_manager, data = init_config(config_file)

    if args.pair:
        if args.address:
            address = args.address
        else:
            address = find_ble_device('Nuki_.*', logger)

        bridge_public_key, bridge_private_key = _generate_bridge_keys()
        nuki = Nuki(address, None, None, bridge_public_key, bridge_private_key)
        nuki_manager.add_nuki(nuki)

        loop = asyncio.get_event_loop()

        def pairing_completed(paired_nuki):
            logger.info(f"Pairing completed, nuki_public_key: {paired_nuki.nuki_public_key.hex()}")
            logger.info(f"Pairing completed, auth_id: {paired_nuki.auth_id.hex()}")
            loop.stop()
        loop.create_task(nuki.pair(pairing_completed))
        loop.run_forever()
    else:
        if not nuki_manager.device_list:
            _add_devices_to_manager(data, nuki_manager)

        if args.unlock:
            device = nuki_manager.device_list[0]
            asyncio.run(device.unlock())
        elif args.lock:
            device = nuki_manager.device_list[0]
            asyncio.run(device.lock())
        else:
            host = data["server"]["host"]
            port = data["server"]["port"]
            token = data["server"]["token"]
            web_server = WebServer(host, port, token, nuki_manager)
            web_server.start()
