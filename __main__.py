import asyncio
import json
import logging
import random
import yaml
import datetime
import hashlib
import argparse
import uuid
import sys

import nacl
from nacl.public import PrivateKey
from aiohttp import web, ClientSession

from nuki import Nuki, NukiManager, BridgeType, DeviceType

LOG_FORMAT = "%(asctime)s.%(msecs)03d|%(levelname).1s|%(filename)s:%(lineno)d|%(message)s"

logger = logging.getLogger("raspinukibridge")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter(fmt=LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
logger.addHandler(handler)

logging.getLogger("aiohttp").addHandler(handler)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("bleak").addHandler(handler)
logging.getLogger("bleak").setLevel(logging.ERROR)


class WebServer:

    def __init__(self, host, port, token, server_id, nuki_manager):
        self._host = host
        self._port = port
        self._token = token
        self._hashed_token = hashlib.sha256(str(self._token).encode('utf-8')).digest()
        self._hashed_token_box = nacl.secret.SecretBox(self._hashed_token)
        self._used_token = {}
        self.nuki_manager = nuki_manager
        self._start_datetime = None
        self._server_id = server_id & 0xFFFFFFFF  # Truncate server_id to 32 bit, OpenHub doesn't like it too big
        self._http_callbacks = [None, None, None]  # Nuki Bridge support up to 3 callbacks

    def start(self):
        app = web.Application()
        app.add_routes([web.get('/info', self.nuki_info),
                        web.get('/list', self.nuki_list),
                        web.get('/lock', self.nuki_lock),
                        web.get('/unlock', self.nuki_unlock),
                        web.get('/lockAction', self.nuki_lockaction),
                        web.get('/lockState', self.nuki_state),
                        web.get('/callback/add', self.callback_add),
                        web.get('/callback/list', self.callback_list),
                        web.get('/callback/remove', self.callback_remove)])
        app.on_startup.append(self._startup)
        web.run_app(app, host=self._host, port=self._port)

    @staticmethod
    def _get_nuki_last_state(nuki):
        state = {"mode": nuki.last_state["nuki_state"].value,
                 "state": nuki.last_state["lock_state"].value,
                 "stateName": nuki.last_state["lock_state"].name,
                 "batteryCritical": nuki.is_battery_critical,
                 "batteryCharging": nuki.is_battery_charging,
                 "batteryChargeState": nuki.battery_percentage,
                 "keypadBatteryCritical": False,  # How to get this from bt api?
                 "doorsensorState": nuki.last_state["door_sensor_state"].value,
                 "doorsensorStateName": nuki.last_state["door_sensor_state"].name,
                 "ringactionTimestamp": None,  # How to get this from bt api?
                 "ringactionState": None,  # How to get this from bt api?
                 "timestamp": nuki.last_state["current_time"].isoformat().split(".")[0],
                 "success": True,
                 }

        if nuki.device_type == DeviceType.OPENER:
            state["ringactionTimestamp"] = nuki.last_state["current_time"].isoformat().split(".")[0]
            state["ringactionState"] = nuki.last_state["last_lock_action_completion_status"]

        return state

    async def _newstate(self, nuki):
        logger.info(f"Nuki new state: {nuki.last_state}")
        if any(self._http_callbacks):
            async with ClientSession() as session:
                for url in filter(None, self._http_callbacks):
                    try:
                        data = {"nukiId": nuki.config["id"],
                                "deviceType": nuki.device_type.value}  # How to get this from bt api?
                        data.update(self._get_nuki_last_state(nuki))
                        async with session.post(url, data=json.dumps(data)) as resp:
                            await resp.text()
                    except:
                        logger.exception(f"Error on http callbak {url}")

    async def _startup(self, _app):
        self._start_datetime = datetime.datetime.now()
        await self.nuki_manager.start_scanning()

    async def callback_add(self, request):
        if not self._check_token(request):
            raise web.HTTPForbidden()
        callback_url = request.query["url"]
        for i, call in enumerate(self._http_callbacks):
            if not call:
                self._http_callbacks[i] = callback_url
                break
        if not self.nuki_manager.newstate_callback:
            self.nuki_manager.newstate_callback = self._newstate
        logger.info(f"Add http callback: {callback_url}")
        return web.Response(text=json.dumps({"success": True}))

    async def callback_list(self, request):
        if not self._check_token(request):
            raise web.HTTPForbidden()
        resp = {"callbacks": [{"id": url_id, "url": url} for url_id, url in enumerate(self._http_callbacks) if url]}
        return web.Response(text=json.dumps(resp))

    async def callback_remove(self, request):
        if not self._check_token(request):
            raise web.HTTPForbidden()
        url_id = request.query["id"]
        self._http_callbacks[int(url_id)] = None
        return web.Response(text=json.dumps({"success": True}))

    async def nuki_list(self, request):
        if not self._check_token(request):
            raise web.HTTPForbidden()
        resp = [{"nukiId": nuki.config["id"],
                 "deviceType": nuki.device_type.value,  # How to get this from bt api?
                 "name": nuki.config["name"],
                 "lastKnownState": self._get_nuki_last_state(nuki)} for nuki in self.nuki_manager if nuki.config]
        return web.Response(text=json.dumps(resp))

    async def nuki_info(self, request):
        if not self._check_token(request):
            raise web.HTTPForbidden()
        resp = {"bridgeType": BridgeType.SW.value,
                # The hardwareId and firmwareVersion should not be sent if bridgeType is BRIDGE_SW,
                # but the homeassistant integration expects it
                "ids": {"hardwareId": self._server_id, "serverId": self._server_id},
                "versions": {"appVersion": "0.1.0", "firmwareVersion": "0.1.0"},
                "uptime": (datetime.datetime.now() - self._start_datetime).seconds,
                "currentTime": datetime.datetime.now().isoformat()[:-7] + "Z",
                "serverConnected": False,
                "scanResults": [{"nukiId": nuki.config["id"],
                                 "type": nuki.device_type.value,  # How to get this from bt api?
                                 "name": nuki.config["name"],
                                 "rssi": nuki.rssi,
                                 "paired": True} for nuki in self.nuki_manager if nuki.config]}
        return web.Response(text=json.dumps(resp))

    def _clear_old_ctokens(self):
        for ctk in list(self._used_token.keys()):
            diff = (datetime.datetime.utcnow() - self._used_token[ctk]).total_seconds()
            if diff > 60:
                del self._used_token[ctk]

    def _check_token(self, request):
        if "hash" in request.query:
            rnr = request.query["rnr"]
            ts = request.query["ts"]
            hash_256 = hashlib.sha256(f"{ts},{rnr},{self._token}".encode("utf-8")).hexdigest()
            return hash_256 == request.query["hash"]
        elif "token" in request.query:
            return self._token == request.query["token"]
        elif "ctoken" in request.query:
            nonce = bytes.fromhex(request.query["nonce"])
            ctoken = bytes.fromhex(request.query["ctoken"])
            self._clear_old_ctokens()
            if ctoken not in self._used_token:
                ts, rnr = self._hashed_token_box.decrypt(ctoken, nonce).decode().split(",")
                ts = datetime.datetime.fromisoformat(ts[:-1])
                diff = (datetime.datetime.utcnow() - ts).total_seconds()
                self._used_token[ctoken] = ts
                return diff <= 60
        return False

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
        return web.Response(text=json.dumps(self._get_nuki_last_state(n)))

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


def _add_devices_to_manager(data, nuki_manager):
    for ls in data["smartlock"]:
        address = ls["address"].lower()
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
    parser.add_argument("--pair", metavar=('MAC_ADDRESS',), help="Pair to a nuki smartlock")
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
        app_id = random.getrandbits(32)
        token = random.getrandbits(256).to_bytes(32, "little").hex()
        server_id = uuid.getnode()
        print(f"server:\n"
              f"  host: 0.0.0.0\n"
              f"  port: 8080\n"
              f"  name: RaspiNukiBridge\n"
              f"  app_id: {app_id}\n"
              f"  token: {token}\n"
              f"  id: {server_id}\n")
        exit(0)

    config_file = args.config or "nuki.yaml"
    with open(config_file) as f:
        data = yaml.load(f, Loader=yaml.FullLoader)

    if "id" not in data["server"]:
        data["server"]["id"] = uuid.getnode()
        with open(config_file, "w") as f:
            yaml.dump(data, f)

    name = data["server"]["name"]
    app_id = data["server"]["app_id"]
    bt_adapter = data["server"].get("adapter", "hci0")

    nuki_manager = NukiManager(name, app_id, bt_adapter)

    if args.pair:
        address = args.pair
        logger.info(f"Generatig keys for Nuki {address}")
        keypair = PrivateKey.generate()
        bridge_public_key = keypair.public_key.__bytes__()
        bridge_private_key = keypair.__bytes__()
        logger.info(f"bridge_public_key: {bridge_public_key.hex()}")
        logger.info(f"bridge_private_key: {bridge_private_key.hex()}")
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
            server_id = data["server"]["id"]
            web_server = WebServer(host, port, token, server_id, nuki_manager)
            web_server.start()
