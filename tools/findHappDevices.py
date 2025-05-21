# 2024-07-02 Alexander Ström
# This component searches for nearby BLE devices with UUIDs only

import asyncio
import configparser
import json
from bleak import BleakScanner
import eel
import logging
from json.decoder import JSONDecodeError
from webserver import getDeviceAlias, getDeviceKey
from SessionData import sessionData

devices = {}

# Create a ConfigParser object
config = configparser.ConfigParser()

# Read the configuration file
config.read('config.ini')

async def scanAndPrint(timeout):
    logging.info(f"Scanning for BLE devices with UUIDs")
    eel.controlLoader(1)

    async def callback(device, advertisement_data):
        try:
            # Only include devices that advertise service UUIDs
            if advertisement_data.service_uuids:  # Check if UUIDs exist
                # Use the first service UUID as the identifier
                uuid = advertisement_data.service_uuids[0]
                rssi = advertisement_data.rssi
                # Store MAC address and RSSI, using UUID as key
                devices[uuid] = (device.address, rssi)
        except:
            pass

    scanner = BleakScanner(detection_callback=callback)

    try:
        await scanner.start()
        await asyncio.sleep(timeout)
    except OSError as e:
        if "The device is not ready for use" in str(e):
            logging.warning("Cannot find Bluetooth on the machine. Please ensure it is turned on!")
            eel.addToLog(str(f"Cannot find Bluetooth on the machine. Please ensure it is turned on!"),
                        "HAPPfinder")
            eel.controlLoader(0)
    finally:
        await scanner.stop()

@eel.expose
def startSearch(timeout=None):
    if timeout is None:
        timeout = 40

    logging.debug(f"Starting BLE device search with timeout set to: {timeout}")
    aliasLookupExists = True
    keyLookupExists = True
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(scanAndPrint(timeout))

    arrayOfDevices = []
    print("\n")
    eel.addToLog(str("\n"))
    counter = 0
    eel.controlLoader(0)

    for uuid, (mac, rssi) in devices.items():
        deviceAlias = ""
        keyShort = ""
        # Use UUID as the primary identifier
        iprid = uuid
        
        counter = counter + 1

        # Check if alias exist to the device
        if not getDeviceAlias(iprid):
            aliasLookupExists = False
        elif getDeviceAlias(iprid) != "unknown":
            deviceAlias = getDeviceAlias(iprid)

        # Check if a key exists to the device
        if not getDeviceKey(iprid):
            keyLookupExists = False
        elif getDeviceKey(iprid) != "unknown":
            key = getDeviceKey(iprid)
            keyShort = key[:8] + "*" * len(key[8::])

        eel.addNewDevice(mac, iprid, 0, 0, rssi, deviceAlias, keyShort)  # Added to frontend
        newDevice = {"mac": mac, "uuid": iprid, "NTC": 0, "DNC": 0, "rssi": str(rssi), "alias": deviceAlias}
        arrayOfDevices.append(newDevice)

    eel.putRLog(f"find.py: New devices: {str(arrayOfDevices)}")
    if not aliasLookupExists:
        eel.addToLog(str(f"No alias lookup file found, alias wont be saved!"),
                    "HAPPfinder")
    if not keyLookupExists:
        eel.addToLog(str(f"No secrets lookup file found, key wont be saved!"),
                    "HAPPfinder")
    print(f"Found {counter} BLE devices with UUIDs")
    eel.addToLog(str(f"Found {counter} BLE devices with UUIDs"), "HAPPfinder")
    sessionData.lastHAPPScan = arrayOfDevices
    return arrayOfDevices