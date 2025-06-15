# Description: BLE Interface
# Author: Syncore Technologies AB
#
# Alexander Ström 2024-06-19
# Newer BLE modules (Hqv BLE Service Frame) seems to send only one packet containing three
# messages, so notify was modified to split buffer (hard coded sizes) and send such packets as three individual UDP
# messages. This seems to work so far, but the new advertisement structure has not been verified by BLE module
# developers yet. Notify sends only one message if nothing is left in the buffer. Otherwise also sends multiple
# buffer messages. A better way would be to not use hard coded fixed sizes. But only encrypted messages have been
# analyzed during this fix, so another way is needed to analyze and fix this.
# -----------------------------------------------------------------
import configparser
import sys
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
import logging, asyncio
from typing import Optional
import BleToUdpPayload
import time
import eel
from webserver import clearDeviceData
from SessionData import sessionData

# Create a ConfigParser object
config = configparser.ConfigParser()

# Read the configuration file
config.read('config.ini')

# Timeout value for BleakClient
bleTimeout = int(config.get("BLE", "Timeout", fallback="40"))

class BLE_interface:
    async def start(
            self,
            addr_str,
            addr_type,
            adapter,
            write_uuid,
            read_uuid,
            timeout_,
            callback,
            autoreconnect,
            callstop,
            excpWinrtEvent,
    ):
        self._ITS_cb = callback
        self._send_queue = asyncio.Queue()
        self._connected = False
        self._addr_str = addr_str
        self._callstop = callstop
        self._adapter = adapter
        self._addr_type = addr_type
        self._read_uuid = read_uuid
        self._write_uuid = write_uuid

        self.requestedDisconnect = False
        self.autoReconnectInProgress = False

        self._autoreconnect = autoreconnect

        self._excpWinrtEvent = excpWinrtEvent

        if sys.platform == "win32":
            try:
                from bleak.backends.winrt.util import allow_sta
                allow_sta()
            except ImportError:
                logging.warning("uninitialize_sta import error")
                pass

        if timeout_ is None:
            timeout = bleTimeout
        else:
            timeout = timeout_

        logging.info(f"Searching for {addr_str}")
        
        MAX_SCAN_RETRIES = 3
        SCAN_TIMEOUT = 15  # Shorter search time per scan, e.g., 15 seconds

        device = None
        for attempt in range(1, MAX_SCAN_RETRIES + 1):
            logging.info(f"Scan attempt {attempt} for {addr_str}")
            device = await BleakScanner.find_device_by_address(addr_str, SCAN_TIMEOUT)
    
            if device is not None:
                break  # Found the device, no need to retry
            else:
                logging.warning(f"Attempt {attempt}: Device not found.")

        #device = await BleakScanner.find_device_by_address(addr_str, 90)
        # logging.debug(f"Device found: {device}")
        # device_data = BleakScanner.advertisement_data(addr_str)
        # logging.debug(f"Device_Data: {device_data}")

        if device is None:
            logging.info("Device not found, try again later")
            eel.putRLog(f"ble_interface.py: Device not found, try again later")
            eel.changeConnectStatus("Device not found, try again later")
            sessionData.connectStatusCode = 4  # 4 indicates error
            self._ITS_cb("Connected: NO", addr_str)
            raise Exception("No devices found, try again later")
        else:
            try:
                logging.info(f"Device found, trying to connect with {addr_str}")
                eel.putRLog(f"ble_interface.py: Device found, trying to connect with {addr_str}")
                self.dev = BleakClient(
                    addr_str, timeout=bleTimeout ,adapter=adapter, address_type=addr_type, disconnected_callback=self.handle_disconnect
                )
                # self.dev = BleakClient(addr_str, disconnected_callback=self.handle_disconnect)
                #await self.dev.connect()
                # Retry connection up to 5 times
                max_retries = 5
                for attempt in range(1, max_retries + 1):
                    try:
                        await self.dev.connect()
                        break  # Exit loop if connection is successful
                    except Exception as e:
                        logging.warning(f"Attempt {attempt} to connect failed: {e}")
                        eel.putRLog(f"ble_interface.py: Attempt {attempt} to connect failed: {e}")
                        if attempt == max_retries:
                            raise  # Re-raise exception if all attempts fail
                        await asyncio.sleep(1)  # Wait before retrying
                sessionData.connectedDeviceMac = str(self.dev.address)
                sessionData.connectStatusCode = 1 # Indicates that a device is connected successfully
                logging.info(f"Device {self.dev.address} connected")
                eel.putRLog(f"ble_interface.py: Device {self.dev.address} connected")
                eel.changeConnectStatus(self.dev.address, True)
                self._ITS_cb("Connected: YES", addr_str)
                self.write_char = self.find_char(write_uuid, "write-without-response")
                self.read_char = self.find_char(read_uuid, "notify")
                self._bletoudp = BleToUdpPayload.BleToUdpPayload()
                await self.dev.start_notify(self.read_char, self.handle_notify)
                self._connected = True

            except Exception as e:
                logging.warning(e)
                eel.changeConnectStatus(e)
                sessionData.connectStatusCode = 4
                pass

    def find_char(self, uuid: Optional[str], req_prop: str) -> BleakGATTCharacteristic:
        found_char = None

        uuid_candidates = uuid

        for srv in self.dev.services:
            for c in srv.characteristics:
                if c.uuid in uuid_candidates:
                    found_char = c
                    logging.debug(f"Found {req_prop} characteristic {c}")
                    break

        # Check if it has the required properties
        assert found_char, "No characteristic with specified UUID found!"
        assert (
                req_prop in found_char.properties
        ), f"Specified characteristic has no {req_prop} property!"

        return found_char

    def set_receiver(self, callback):
        self._cb = callback
        logging.info("BLE Receiver set up")

    async def send_loop(self):
        assert hasattr(self, "_cb"), "Callback must be set before receive loop!"
        while True:
            data = await self._send_queue.get()
            if data == None:
                logging.debug(f"Break BLE Send Loop")
                break  # Let the future end on shutdown
            logging.debug(f"Write BLE: ({len(data)}) {data}")
            eel.putRLog(f"ble_interface.py: Write BLE: ({len(data)})")
            await self.dev.write_gatt_char(self.write_char, data)

    def stop_loop(self):
        logging.info("Stopping Bluetooth event loop")
        self.requestedDisconnect = True
        self._send_queue.put_nowait(None)

    async def disconnect(self):
        # Wait for the disconnect event
        await asyncio.sleep(5)
        if hasattr(self, "dev"):

            if self.dev.is_connected and self._connected:
                logging.debug("Bluetooth still connected")
                if hasattr(self, "read_char"):
                    await self.dev.stop_notify(self.read_char)
                self.dev.set_disconnected_callback(None) # Otherwise disconnect callback is triggered when wanting to disconnect the device
                disconnectTask = asyncio.create_task(self.dev.disconnect())
                # Winrt on windows is unstable, so if the main disconnect fails with winrt error (reported with
                # _excpWinrtEvent in triggerContinue) continue with gateway termination
                triggerContinueTask = asyncio.create_task(self.triggerContinue())
                done, pending = await asyncio.wait(
                    [disconnectTask, triggerContinueTask],
                    return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        logging.debug("A pending task in disconnect was cancelled")
                for task in done:
                    if task == disconnectTask:
                        logging.debug("BLE device disconnected correctly")
                        sessionData.connectStatusCode = 2
                    elif task == triggerContinueTask:
                        logging.debug("BLE device disconnected unsafely")
                        sessionData.connectStatusCode = 4
                self._connected = False
                logging.info("Bluetooth disconnected")
                eel.putRLog(f"ble_interface.py: Bluetooth disconnected")
                eel.changeConnectStatus("Disconnected")
                clearDeviceData()

    # Continue with the disconnection process
    async def triggerContinue(self):
        while True:
            if self._excpWinrtEvent.is_set():
                return
            await asyncio.sleep(1)

    def queue_send(self, data: bytes):
        # logging.debug('queue_send')
        self._send_queue.put_nowait(data)

    def handle_notify(self, handle: int, data: bytes):
        logging.debug(f"Received BLE: ({len(data)})  {data}")
        eel.putRLog(f"ble_interface.py: Received BLE: ({len(data)})")

        udpmessage = self._bletoudp.Convert(data)  # {Payload , Type}
        logging.debug(f"Buffer Size: {len(self._bletoudp.messageBuffer)}")

        # Handle the first (or only) UDP message
        if not (udpmessage is None) and (udpmessage[1] == 3):  # Remote Server
            self._cb(udpmessage[0])
            logging.debug(f"To Remote Server")
        elif not (udpmessage is None) and (udpmessage[1] == 2):  # Local Server
            logging.debug(f"To Local Server, FG")

        # If message in buffer - Used for handling a combined message
        run = True # Used for debug
        if len(self._bletoudp.messageBuffer) != 0 and run and self._bletoudp.HasCompleteMessageInBuffer():
            # Old HAPP devices with smaller data packages only need this:
            # self._cb(bytearray(self._bletoudp.messageBuffer))

            # Newer HAPP devices and advertisement structure needs split UDP messages during registration (might also
            # be other packages), but this will also work for the rest of all messages for all devices (But unsure if
            # the client is concatenating these)
            logging.debug(f"Sending split buffer msg: {self._bletoudp.messageBuffer}")
            msg1 = bytearray(self._bletoudp.messageBuffer[4: 18])
            #logging.debug(f"First message in buffer: {msg1}")
            self._cb(msg1)

            # Send next message in buffer
            msg2 = bytearray(self._bletoudp.messageBuffer[22:])
            #logging.debug(f"Second message in buffer: {msg2}")
            self._cb(msg2)

    # Alexander Ström 2024-07-19
    # problem with reconnecting on windows because of winrt. Might fix in future bleak and
    # or windows fix. Another backend than winrt can be a fix. Error is [WinError -2147483629].
    # This is not a requested functionality, so for now auto reconnect is inactivated on Windows.
    def handle_disconnect(self, client: BleakClient):
        if self._connected and not self.autoReconnectInProgress:
            logging.warning(f"Device {client.address} disconnected")
            eel.putRLog(f"ble_interface.py: Device {client.address} disconnected")
            if sessionData.deviceConnectedToLeshan == "False":
                sessionData.connectStatusCode = 6
                eel.changeConnectStatus("Connection lost, failed to register to Leshan!")
            else:
                sessionData.connectStatusCode = 5
                eel.changeConnectStatus("Connection lost")

            clearDeviceData()
            logging.debug(f"Auto reconnect is {self._autoreconnect}")
            if sys.platform == "win32" and self._autoreconnect:
                logging.debug(f"Auto reconnect workaround on Windows starting")
                eel.putRLog("ble_interface.py: Auto reconnect workaround on Windows starting")
                self.autoReconnectInProgress = True
                asyncio.ensure_future(self.do_reconnect(self._addr_str))
            else:
                logging.debug("Auto reconnect inactive or unsupported")
                eel.putRLog("ble_interface.py: Auto reconnect inactive or unsupported")
                self._connected = False
                self._ITS_cb("BT Disconnected", client.address)
                raise BleakError(f"{client.address} disconnected!")

    async def do_reconnect(self, address: str):
        MAX_RETRIES = 5
        DELAY = 10
        for attempt in range(1, MAX_RETRIES + 1):
            if self.requestedDisconnect:
                return

            logging.info(f"Reconnect attempt {attempt} for {address}")
            eel.putRLog(f"ble_interface.py: Reconnect attempt {attempt} for {address}")
            try:
                device = await BleakScanner.find_device_by_address(address, timeout=30.0)
                if not device:
                    logging.warning("Device not found during reconnect scan")
                    await asyncio.sleep(DELAY)
                    continue

                new_client = BleakClient(
                    device,
                    adapter=self._adapter,
                    address_type=self._addr_type,
                    disconnected_callback=self.handle_disconnect
                )
                await new_client.connect(timeout=20)

                self.dev = new_client
                self.write_char = self.find_char(self._write_uuid, "write-without-response")
                self.read_char = self.find_char(self._read_uuid, "notify")

                await self.dev.start_notify(self.read_char, self.handle_notify)

                self._connected = True
                self.autoReconnectInProgress = False
                sessionData.connectedDeviceMac = address
                eel.changeConnectStatus(address, True)
                logging.info(f"Auto reconnect succeeded")
                eel.putRLog("ble_interface.py: Auto reconnect succeeded")
                return

            except Exception as e:
                logging.warning(f"Reconnect attempt {attempt} failed: {e}")
                eel.putRLog(f"ble_interface.py: Reconnect attempt {attempt} failed: {e}")
                await asyncio.sleep(DELAY)

        logging.warning("Auto reconnect failed after all attempts")
        eel.putRLog("ble_interface.py: Auto reconnect failed after all attempts")
        self._connected = False
        self.autoReconnectInProgress = False
        self._ITS_cb("BT Disconnected", address)
        raise BleakError(f"{address} disconnected!")