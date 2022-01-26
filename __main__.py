import asyncio
import json
import logging
import random
import yaml
import datetime
import hashlib
import argparse
import uuid

from nacl.public import PrivateKey
from aiohttp import web

from nuki import Nuki, NukiManager, BridgeType, DeviceType

logging.basicConfig(level=logging.INFO)


class WebServer:

    def __init__(self, host, port, token, nuki_manager):
        self._host = host
        self._port = port
        self._token = token
        self.nuki_manager = nuki_manager
        self._start_datetime = None
        self._server_id = uuid.getnode()

    def start(self):
        app = web.Application()
        app.add_routes([web.get('/info', self.nuki_info),
                        web.get('/list', self.nuki_list),
                        web.get('/lock', self.nuki_lock),
                        web.get('/unlock', self.nuki_unlock),
                        web.get('/lockAction', self.nuki_lockaction),
                        web.get('/lockState', self.nuki_state)])
        app.on_startup.append(self._startup)
        web.run_app(app, host=self._host, port=self._port)

    async def _startup(self, _app):
        self._start_datetime = datetime.datetime.now()
        await self.nuki_manager.start_scanning()

    async def nuki_list(self, request):
        if not self._check_token(request):
            raise web.HTTPForbidden()
        resp = [{"nukiId": nuki.config["id"],
                 "deviceType":  DeviceType.SMARTLOCK_1_2.value,  # How to get this from bt api?
                 "name": nuki.config["name"],
                 "lastKnownState": {
                     "mode": nuki.last_state["nuki_state"],
                     "state": nuki.last_state["lock_state"].value,
                     "stateName": nuki.last_state["lock_state"].name,
                     "batteryCritical": nuki.is_battery_critical,
                     "batteryChargeState": nuki.battery_percentage,
                     "keypadBatteryCritical": False,  # How to get this from bt api?
                     "doorsensorState": nuki.last_state["door_sensor_state"].value,
                     "doorsensorStateName": nuki.last_state["door_sensor_state"].name,
                     "ringactionTimestamp": None,  # How to get this from bt api?
                     "ringactionState": None,  # How to get this from bt api?
                     "timestamp": nuki.last_state["current_time"].isoformat()[:-7],
                 }} for nuki in self.nuki_manager if nuki.config]
        return web.Response(text=json.dumps(resp))

    async def nuki_info(self, request):
        if not self._check_token(request):
            raise web.HTTPForbidden()
        resp = {"bridgeType": BridgeType.SW.value,
                # The hardwareId should not be sent if bridgeType is BRIDGE_SW, but the homeassistant
                # integration expects it
                "ids": {"hardwareId": self._server_id, "serverId": self._server_id},
                "versions": {"appVersion": "0.1.0"},
                "uptime": (datetime.datetime.now() - self._start_datetime).seconds,
                "currentTime": datetime.datetime.now().isoformat()[:-7] + "Z",
                "serverConnected": False,
                "scanResults": [{"nukiId": nuki.config["id"],
                                 "type": DeviceType.SMARTLOCK_1_2.value,  # How to get this from bt api?
                                 "name": nuki.config["name"],
                                 "rssi": nuki.rssi,
                                 "paired": True} for nuki in self.nuki_manager if nuki.config]}
        return web.Response(text=json.dumps(resp))

    def _check_token(self, request):
        if "hash" in request.query:
            rnr = request.query["rnr"]
            ts = request.query["ts"]
            hash_256 = hashlib.sha256(f"{ts},{rnr},{self._token}".encode("utf-8")).hexdigest()
            return hash_256 == request.query["hash"]
        return False  # self._token == request.query["token"]

    async def nuki_lockaction(self, request):
        if not self._check_token(request):
            raise web.HTTPForbidden()
        action = int(request.query["action"])
        n = self.nuki_manager.nuki_by_id(int(request.query["nukiId"]))
        await n.lock_action(action)
        res = json.dumps({"success": True, "batteryCritical": n.is_battery_critical})
        return web.Response(text=res)

    async def nuki_state(self, request):
        if not self._check_token(request):
            raise web.HTTPForbidden()
        n = self.nuki_manager.nuki_by_id(int(request.query["nukiId"]))
        return web.Response(text=json.dumps(n.last_state))

    async def nuki_lock(self, request):
        if not self._check_token(request):
            raise web.HTTPForbidden()
        n = self.nuki_manager.nuki_by_id(int(request.query["nukiId"]))
        await n.lock()
        res = json.dumps({"success": True, "batteryCritical": n.is_battery_critical})
        return web.Response(text=res)

    async def nuki_unlock(self, request):
        if not self._check_token(request):
            raise web.HTTPForbidden()
        n = self.nuki_manager.nuki_by_id(int(request.query["nukiId"]))
        await n.unlock()
        res = json.dumps({"success": True, "batteryCritical": n.is_battery_critical})
        return web.Response(text=res)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", metavar=('CONFIG_FILE',), help="Specify the yaml file to use")
    parser.add_argument("--pair", metavar=('MAC_ADDRESS',), help="Pair to a nuki smartlock")
    parser.add_argument("--generate-config", action='store_true', help="Generate a new configuration file")
    args = parser.parse_args()

    if args.generate_config:
        app_id = random.getrandbits(32)
        token = random.getrandbits(256).to_bytes(32, "little").hex()
        print(f"server:\n"
              f"  host: 0.0.0.0\n"
              f"  port: 8080\n"
              f"  name: RaspiNukiBridge\n"
              f"  app_id: {app_id}\n"
              f"  token: {token}\n")
        exit(0)

    config_file = args.config or "nuki.yaml"
    with open(config_file) as f:
        data = yaml.load(f, Loader=yaml.FullLoader)

    name = data["server"]["name"]
    app_id = data["server"]["app_id"]

    nuki_manager = NukiManager(name, app_id)

    if args.pair:
        address = args.pair
        logging.info(f"Generatig keys for Nuki {address}")
        keypair = PrivateKey.generate()
        bridge_public_key = keypair.public_key.__bytes__()
        bridge_private_key = keypair.__bytes__()
        logging.info(f"bridge_public_key: {bridge_public_key.hex()}")
        logging.info(f"bridge_private_key: {bridge_private_key.hex()}")
        nuki = Nuki(address, None, None, bridge_public_key, bridge_private_key)
        nuki_manager.add_nuki(nuki)

        loop = asyncio.get_event_loop()

        def pairing_completed(paired_nuki):
            logging.info(f"Pairing completed, nuki_public_key: {paired_nuki.nuki_public_key.hex()}")
            logging.info(f"Pairing completed, auth_id: {paired_nuki.auth_id.hex()}")
            loop.stop()
        loop.create_task(nuki.pair(pairing_completed))
        loop.run_forever()
    else:
        for ls in data["smartlock"]:
            address = ls["address"]
            auth_id = bytes.fromhex(ls["auth_id"])
            nuki_public_key = bytes.fromhex(ls["nuki_public_key"])
            bridge_public_key = bytes.fromhex(ls["bridge_public_key"])
            bridge_private_key = bytes.fromhex(ls["bridge_private_key"])
            nuki_manager.add_nuki(Nuki(address, auth_id, nuki_public_key, bridge_public_key, bridge_private_key))

        host = data["server"]["host"]
        port = data["server"]["port"]
        token = data["server"]["token"]
        web_server = WebServer(host, port, token, nuki_manager)
        web_server.start()
