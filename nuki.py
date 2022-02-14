import asyncio
import datetime
import hashlib
import logging
import struct
import hmac
import enum

import crc16
import nacl.utils
import nacl.secret
from nacl.bindings.crypto_box import crypto_box_beforenm
from bleak import BleakScanner, BleakClient


BLE_SERVICE_CHAR = "a92ee202-5501-11e4-916c-0800200c9a66"
BLE_PAIRING_CHAR = 'a92ee101-5501-11e4-916c-0800200c9a66'


class BridgeType(enum.Enum):
    HW = 1
    SW = 2


class DeviceType(enum.Enum):
    SMARTLOCK_1_2 = 0
    OPENER = 1
    SMARTDOOR = 2
    SMARTLOCK_3 = 3


class DoorsensorState(enum.Enum):
    DEACTIVATED = 1
    DOOR_CLOSED = 2
    DOOR_OPENED = 3
    DOOR_STATE_UNKOWN = 4
    CALIBRATING = 5
    UNCALIBRATED = 16
    REMOVED = 240
    UNKOWN = 255


class NukiCommand(enum.Enum):
    REQUEST_DATA = 0x0001
    PUBLIC_KEY = 0x0003
    CHALLENGE = 0x0004
    AUTH_AUTHENTICATOR = 0x0005
    AUTH_DATA = 0x0006
    AUTH_ID = 0x0007
    KEYTURNER_STATES = 0x000C
    LOCK_ACTION = 0x000D
    STATUS = 0x000E
    ERROR_REPORT = 0x0012
    REQUEST_CONFIG = 0x0014
    CONFIG = 0x0015
    AUTH_ID_CONFIRM = 0x001E


class NukiState(enum.Enum):
    UNCALIBRATED = 0x00
    LOCKED = 0x01
    UNLOCKING = 0x02
    UNLOCKED = 0x03
    LOCKING = 0x04
    UNLATCHED = 0x05
    UNLOCKED_LOCK_N_GO = 0x06
    UNLATCHING = 0x07
    CALIBRATION = 0xFC
    BOOT_RUN = 0xFD
    MOTOR_BLOCKED = 0xFE
    UNDEFINED = 0xFF


class NukiAction(enum.Enum):
    NONE = 0x00
    UNLOCK = 0x01
    LOCK = 0x02
    UNLATCH = 0x03
    LOCK_N_GO = 0x04
    LOCK_N_GO_UNLATCH = 0x05
    FULL_LOCK = 0x06
    FOB_ACTION_1 = 0x81
    FOB_ACTION_2 = 0x82
    FOB_ACTION_3 = 0x83


class NukiClientType(enum.Enum):
    APP = 0x00
    BRIDGE = 0x01
    FOB = 0x02
    KEYPAD = 0x03


logger = logging.getLogger("raspinukibridge")


class NukiManager:

    def __init__(self, name, app_id, adapter="hci0"):
        self.name = name
        self.app_id = app_id
        self.type_id = NukiClientType.BRIDGE
        self.newstate_callback = None

        self._adapter = adapter
        self._devices = {}
        self._scanner = BleakScanner(adapter=self._adapter)
        self._scanner.register_detection_callback(self._detected_ibeacon)

    async def nuki_newstate(self, nuki):
        if self.newstate_callback:
            await self.newstate_callback(nuki)

    def get_client(self, address):
        return BleakClient(address, adapter=self._adapter)

    def __getitem__(self, index):
        return list(self._devices.values())[index]

    def nuki_by_id(self, nuki_id):
        return next(nuki for nuki in self._devices.values() if nuki.config.get("id") == nuki_id)

    def add_nuki(self, nuki: 'Nuki'):
        nuki.manager = self
        self._devices[nuki.address] = nuki

    async def start_scanning(self):
        logger.info("Start scanning")
        await self._scanner.start()

    async def stop_scanning(self):
        logger.info("Stop scanning")
        try:
            await self._scanner.stop()
        except:
            pass

    async def _detected_ibeacon(self, device, advertisement_data):
        if device.address in self._devices:
            logger.info(f"Nuki: {device.address}, RSSI: {device.rssi} {advertisement_data}")
            nuki = self._devices[device.address]
            nuki.set_ble_device(device)
            nuki.rssi = device.rssi
            if not nuki.last_state or list(advertisement_data.manufacturer_data.values())[0][-1] == 0xC5:
                await nuki.update_state()


class Nuki:

    def __init__(self, address, auth_id, nuki_public_key, bridge_public_key, bridge_private_key):
        self.address = address
        self.auth_id = auth_id
        self.nuki_public_key = nuki_public_key
        self.bridge_public_key = bridge_public_key
        self.bridge_private_key = bridge_private_key
        self.manager = None
        self.id = None
        self.name = None
        self.rssi = None
        self.last_state = None
        self.config = {}

        self._pairing_handle = None
        self._client = None
        self._challenge_command = None
        self._pairing_callback = None

        if nuki_public_key and bridge_private_key:
            self._create_shared_key()

    def _create_shared_key(self):
        self._shared_key = crypto_box_beforenm(self.nuki_public_key, self.bridge_private_key)
        self._box = nacl.secret.SecretBox(self._shared_key)

    @property
    def is_battery_critical(self):
        return bool(self.last_state["critical_battery_state"] & 1)

    @property
    def is_battery_charging(self):
        return bool(self.last_state["critical_battery_state"] & 2)

    @property
    def battery_percentage(self):
        return ((self.last_state["critical_battery_state"] & 252) >> 2) * 2

    @staticmethod
    def _prepare_command(cmd_code: int, payload=bytes()):
        message = cmd_code.to_bytes(2, "little") + payload
        crc = crc16.crc16xmodem(message, 0xffff).to_bytes(2, "little")
        message += crc
        return message

    def _encrypt_command(self, cmd_code: int, payload=bytes()):
        unencrypted = self.auth_id + self._prepare_command(cmd_code, payload)[:-2]
        crc = crc16.crc16xmodem(unencrypted, 0xffff).to_bytes(2, "little")
        unencrypted += crc
        nonce = nacl.utils.random(24)
        encrypted = self._box.encrypt(unencrypted, nonce)[24:]
        length = len(encrypted).to_bytes(2, "little")
        message = nonce + self.auth_id + length + encrypted
        return message

    def _decrypt_command(self, data):
        nonce = data[:24]
        auth_id, length = struct.unpack("<IH", data[24:30])
        encrypted = nonce + data[30:30 + length]
        decrypted = self._box.decrypt(encrypted)
        return decrypted[4:]

    async def _parse_command(self, data):
        command, = struct.unpack("<H", data[:2])
        command = NukiCommand(command)
        #crc = data[-2:]
        data = data[2:-2]
        logger.debug(f"Parsing command: {command}, data: {data}")

        if command == NukiCommand.CHALLENGE:
            return command, {"nonce": data}

        elif command == NukiCommand.KEYTURNER_STATES:
            values = struct.unpack("<BBBHBBBBBHBBBBBBBH", data[:21])
            return command, {"nuki_state": values[0],
                             "lock_state": NukiState(values[1]),
                             "trigger": values[2],
                             "current_time": datetime.datetime(values[3], values[4], values[5],
                                                               values[6], values[7], values[8]),
                             "timezone_offset": values[9],
                             "critical_battery_state": values[10],
                             "current_update_count": values[11],
                             "lock_n_go_timer": values[12],
                             "last_lock_action": NukiAction(values[13]),
                             "last_lock_action_trigger": values[14],
                             "last_lock_action_completion_status": values[15],
                             "door_sensor_state": DoorsensorState(values[16]),
                             "nightmode_active": values[17],
                             # "accessory_battery_state": values[18],  # It doesn't exist?
                             }
        elif command == NukiCommand.CONFIG:
            values = struct.unpack("<I32sffBBBBBHBBBBBhBBBBBBBBBBBBBBH", data[:74])
            return command, {"id": values[0],
                             "name": values[1].split(b"\x00")[0].decode(),
                             "latitude": values[2],
                             "longitude": values[3],
                             "auto_unlatch": values[4],
                             "pairing_enabled": values[5],
                             "button_enabled": values[6],
                             "led_enabled": values[7],
                             "led_brightness": values[8],
                             "current_time": datetime.datetime(values[9], values[10], values[11],
                                                               values[12], values[13], values[14]),
                             "timezone_offset": values[15],
                             "dst_mode": values[16],
                             "has_fob": values[17],
                             "fob_action_1": values[18],
                             "fob_action_2": values[19],
                             "fob_action_3": values[20],
                             "single_lock": values[21],
                             "advertising_mode": values[22],
                             "has_keypad": values[23],
                             "firmware_version": f"{values[24]}.{values[25]}.{values[26]}",
                             "hardware_revision": f"{values[27]}.{values[28]}",
                             "homekit_status": values[29],
                             "timezone_id": values[30],
                             }

        elif command == NukiCommand.PUBLIC_KEY:
            return command, {"public_key": data}

        elif command == NukiCommand.AUTH_ID:
            values = struct.unpack("<32s4s16s32s", data[:84])
            return command, {"authenticator": values[0],
                             "auth_id": values[1],
                             "uuuid": values[2],
                             "nonce": values[3]}

        elif command == NukiCommand.STATUS:
            status = struct.unpack('<B', data[:1])
            logger.error(f"Last action status: {status}")
            return command, {"status": status}

        elif command == NukiCommand.ERROR_REPORT:
            struct.unpack('<bH', data[:3])
            logger.error(f"Error {data}")
            await self.disconnect()
            return command, data

        return None, None

    def set_ble_device(self, ble_device):
        self._client = BleakClient(ble_device)

    async def _notification_handler(self, sender, data):
        logger.debug(f"Notification handler: {sender}, data: {data}")
        if sender == self._client.services[BLE_PAIRING_CHAR].handle:
            # The pairing handler is not encrypted
            command, data = await self._parse_command(bytes(data))
        else:
            uncrypted = self._decrypt_command(bytes(data))
            command, data = await self._parse_command(uncrypted)

        if command == NukiCommand.KEYTURNER_STATES:
            update_config = not self.config or (self.last_state["current_update_count"] != data["current_update_count"])
            self.last_state = data
            logger.info(f"State: {self.last_state}")
            if update_config:
                await self.get_config()
            else:
                await self.disconnect()
            if self.config and self.last_state:
                await self.manager.nuki_newstate(self)

        elif command == NukiCommand.CONFIG:
            self.config = data
            logger.info(f"Config: {self.config}")
            await self.disconnect()
            if self.config and self.last_state:
                await self.manager.nuki_newstate(self)

        elif command == NukiCommand.PUBLIC_KEY:
            self.nuki_public_key = data["public_key"]
            self._create_shared_key()
            logger.info(f"Nuki {self.address} public key: {self.nuki_public_key.hex()}")
            self._challenge_command = NukiCommand.PUBLIC_KEY
            cmd = self._prepare_command(NukiCommand.PUBLIC_KEY.value, self.bridge_public_key)
            await self._send_data(BLE_PAIRING_CHAR, cmd)

        elif command == NukiCommand.AUTH_ID:
            self.auth_id = data["auth_id"]
            value_r = self.auth_id + data["nonce"]
            payload = hmac.new(self._shared_key, msg=value_r, digestmod=hashlib.sha256).digest()
            payload += self.auth_id
            self._challenge_command = NukiCommand.AUTH_ID_CONFIRM
            cmd = self._prepare_command(NukiCommand.AUTH_ID_CONFIRM.value, payload)
            await self._send_data(BLE_PAIRING_CHAR, cmd)

        elif command == NukiCommand.STATUS:
            if self._challenge_command == NukiCommand.AUTH_ID_CONFIRM:
                if self._pairing_callback:
                    self._pairing_callback(self)
                    self._pairing_callback = None

        elif command == NukiCommand.CHALLENGE and self._challenge_command:
            logger.debug(f"Challenge for {self._challenge_command}")
            if self._challenge_command == NukiCommand.REQUEST_CONFIG:
                cmd = self._encrypt_command(NukiCommand.REQUEST_CONFIG.value, data["nonce"])
                await self._send_data(BLE_SERVICE_CHAR, cmd)

            elif self._challenge_command in NukiAction:
                lock_action = self._challenge_command.value.to_bytes(1, "little")
                app_id = self.manager.app_id.to_bytes(4, "little")
                flags = 0
                payload = lock_action + app_id + flags.to_bytes(1, "little") + data["nonce"]
                cmd = self._encrypt_command(NukiCommand.LOCK_ACTION.value, payload)
                await self._send_data(BLE_SERVICE_CHAR, cmd)

            elif self._challenge_command == NukiCommand.PUBLIC_KEY:
                value_r = self.bridge_public_key + self.nuki_public_key + data["nonce"]
                payload = hmac.new(self._shared_key, msg=value_r, digestmod=hashlib.sha256).digest()
                self._challenge_command = NukiCommand.AUTH_AUTHENTICATOR
                cmd = self._prepare_command(NukiCommand.AUTH_AUTHENTICATOR.value, payload)
                await self._send_data(BLE_PAIRING_CHAR, cmd)

            elif self._challenge_command == NukiCommand.AUTH_AUTHENTICATOR:
                app_id = self.manager.app_id.to_bytes(4, "little")
                type_id = self.manager.type_id.value.to_bytes(1, "little")
                name = self.manager.name.encode("utf-8").ljust(32, b"\0")
                nonce = nacl.utils.random(32)
                value_r = type_id + app_id + name + nonce + data["nonce"]
                payload = hmac.new(self._shared_key, msg=value_r, digestmod=hashlib.sha256).digest()
                payload += type_id + app_id + name + nonce
                self._challenge_command = NukiCommand.AUTH_DATA
                cmd = self._prepare_command(NukiCommand.AUTH_DATA.value, payload)
                await self._send_data(BLE_PAIRING_CHAR, cmd)

    async def _send_data(self, characteristic, data):
        # Sometimes the connection to the smartlock fails, retry 3 times
        for _ in range(3):
            try:
                if not self._client.is_connected:
                    await self.connect()
                logger.debug(f"Sending data to {characteristic}: {data}")
                await self._client.write_gatt_char(characteristic, data, True)
            except Exception as exc:
                logger.error(f"Error: {exc}")
                await asyncio.sleep(1)
            else:
                break
        else:
            await self.disconnect()

    async def connect(self):
        if not self._client:
            self._client = self.manager.get_client(self.address)
        await self.manager.stop_scanning()
        logger.info("Nuki connecting")
        await self._client.connect()
        await self._client.start_notify(BLE_PAIRING_CHAR, self._notification_handler)
        await self._client.start_notify(BLE_SERVICE_CHAR, self._notification_handler)
        logger.info("Connected")

    async def disconnect(self):
        logger.info("Nuki disconnecting")
        await self._client.disconnect()
        await self.manager.start_scanning()

    async def update_state(self):
        logger.info("Updating nuki state")
        self._challenge_command = NukiCommand.KEYTURNER_STATES
        payload = NukiCommand.KEYTURNER_STATES.value.to_bytes(2, "little")
        cmd = self._encrypt_command(NukiCommand.REQUEST_DATA.value, payload)
        await self._send_data(BLE_SERVICE_CHAR, cmd)

    async def lock(self):
        logger.info("Locking nuki")
        self._challenge_command = NukiAction.LOCK
        payload = NukiCommand.CHALLENGE.value.to_bytes(2, "little")
        cmd = self._encrypt_command(NukiCommand.REQUEST_DATA.value, payload)
        await self._send_data(BLE_SERVICE_CHAR, cmd)

    async def unlock(self):
        logger.info("Unlocking")
        self._challenge_command = NukiAction.UNLOCK
        payload = NukiCommand.CHALLENGE.value.to_bytes(2, "little")
        cmd = self._encrypt_command(NukiCommand.REQUEST_DATA.value, payload)
        await self._send_data(BLE_SERVICE_CHAR, cmd)

    async def unlatch(self):
        self._challenge_command = NukiAction.UNLATCH
        payload = NukiCommand.CHALLENGE.value.to_bytes(2, "little")
        cmd = self._encrypt_command(NukiCommand.REQUEST_DATA.value, payload)
        await self._send_data(BLE_SERVICE_CHAR, cmd)

    async def lock_action(self, action):
        logger.info(f"Lock action {action}")
        self._challenge_command = NukiAction(action)
        payload = NukiCommand.CHALLENGE.value.to_bytes(2, "little")
        cmd = self._encrypt_command(NukiCommand.REQUEST_DATA.value, payload)
        await self._send_data(BLE_SERVICE_CHAR, cmd)

    async def get_config(self):
        logger.info("Retrieve nuki configuration")
        self._challenge_command = NukiCommand.REQUEST_CONFIG
        payload = NukiCommand.CHALLENGE.value.to_bytes(2, "little")
        cmd = self._encrypt_command(NukiCommand.REQUEST_DATA.value, payload)
        await self._send_data(BLE_SERVICE_CHAR, cmd)

    async def pair(self, callback):
        self._pairing_callback = callback
        self._challenge_command = NukiCommand.PUBLIC_KEY
        payload = NukiCommand.PUBLIC_KEY.value.to_bytes(2, "little")
        cmd = self._prepare_command(NukiCommand.REQUEST_DATA.value, payload)
        await self._send_data(BLE_PAIRING_CHAR, cmd)
