import datetime
import hashlib
import json
import uuid

from aiohttp import web, ClientSession

from utils import logger
from nuki import DeviceType, BridgeType


class WebServer:

    def __init__(self, host, port, token, nuki_manager):
        self._host = host
        self._port = port
        self._token = token
        self.nuki_manager = nuki_manager
        self._start_datetime = None
        self._server_id = uuid.getnode() & 0xFFFFFFFF  # Truncate server_id to 32 bit, OpenHub doesn't like it too big
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
                        data = {"nukiId": hex(nuki.config["id"])[2:],
                                "deviceType": nuki.device_type.value}  # How to get this from bt api?
                        data.update(self._get_nuki_last_state(nuki))
                        async with session.post(url, data=json.dumps(data)) as resp:
                            await resp.text()
                    except:
                        logger.exception(f"Error on http callbak {url}")

    async def _startup(self, _app):
        self._start_datetime = datetime.datetime.now()
        self.nuki_manager.start()

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
        resp = [{"nukiId": hex(nuki.config["id"])[2:],
                 "deviceType": nuki.device_type.value,  # How to get this from bt api?
                 "name": nuki.config["name"],
                 "lastKnownState": self._get_nuki_last_state(nuki)} for nuki in self.nuki_manager if nuki.config]
        logger.info(f'Listed {len(resp)} devices')
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
                "scanResults": [{"nukiId": hex(nuki.config["id"])[2:],
                                 "type": nuki.device_type.value,  # How to get this from bt api?
                                 "name": nuki.config["name"],
                                 "rssi": nuki.rssi,
                                 "paired": True} for nuki in self.nuki_manager if nuki.config]}
        return web.Response(text=json.dumps(resp))

    def _check_token(self, request):
        token_valid = False
        if "hash" in request.query:
            rnr = request.query["rnr"]
            ts = request.query["ts"]
            hash_256 = hashlib.sha256(f"{ts},{rnr},{self._token}".encode("utf-8")).hexdigest()
            token_valid = hash_256 == request.query["hash"]
        elif "token" in request.query:
            token_valid = self._token == request.query["token"]
        if not token_valid:
            logger.error('Invalid token. Please change token.')
        return token_valid

    async def nuki_lockaction(self, request):
        if not self._check_token(request):
            raise web.HTTPForbidden()
        action = int(request.query["action"])
        n = self.nuki_manager.nuki_by_id(int(request.query["nukiId"], base=16))
        await n.lock_action(action)
        res = json.dumps({"success": True, "batteryCritical": n.is_battery_critical})
        return web.Response(text=res)

    async def nuki_state(self, request):
        if not self._check_token(request):
            raise web.HTTPForbidden()
        n = self.nuki_manager.nuki_by_id(int(request.query["nukiId"], base=16))
        return web.Response(text=json.dumps(self._get_nuki_last_state(n)))

    async def nuki_lock(self, request):
        if not self._check_token(request):
            raise web.HTTPForbidden()
        n = self.nuki_manager.nuki_by_id(int(request.query["nukiId"], base=16))
        await n.lock()
        res = json.dumps({"success": True, "batteryCritical": n.is_battery_critical})
        return web.Response(text=res)

    async def nuki_unlock(self, request):
        if not self._check_token(request):
            raise web.HTTPForbidden()
        n = self.nuki_manager.nuki_by_id(int(request.query["nukiId"], base=16))
        await n.unlock()
        res = json.dumps({"success": True, "batteryCritical": n.is_battery_critical})
        return web.Response(text=res)