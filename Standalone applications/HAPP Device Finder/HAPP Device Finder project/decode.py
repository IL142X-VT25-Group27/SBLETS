import asyncio
from bleak import BleakScanner
import eel

devices = {}

async def scan_and_print():
    print("Scanning.", end='')
    eel.controlLoader(1)

    async def callback(device, advertisement_data):
        print(".", end='')
        print(f"{device.address}:")
        print(f"    manufacturer_data={advertisement_data.manufacturer_data}")
        print(f"    service_uuids={advertisement_data.service_uuids}")
        try:
            uuidByte = advertisement_data.service_data["0000fd85-0000-1000-8000-00805f9b34fb"]
            rssi = advertisement_data.rssi
        except:
            uuidByte = None
        if uuidByte is not None:
            eel.addToLog(str(f"Found possible value in device: {device.address}"))
            devices[device.address] = (uuidByte, rssi)

    scanner = BleakScanner(detection_callback=callback)
    
    try:
        await scanner.start()
        await asyncio.sleep(10)  # Skanna i 10 sekunder
    finally:
        await scanner.stop()

@eel.expose
def start_search():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(scan_and_print())

    print("\n")
    eel.addToLog(str("\n"))
    counter = 0
    eel.controlLoader(0)

    arrayOfDevices = []

    for mac, (byteString, rssi) in devices.items():
        byte = bytearray(byteString)
        print(byte)
        uuidRaw = byte[1:-3][::-1]
        uuid = uuidRaw.hex()
        counter = counter + 1

        print(f"{mac}: {uuid}, {rssi}")
        eel.addToLog(str(f"<strong>{mac}: {uuid}, {rssi}</strong>"))
        newDevice = {"mac": mac, "uuid": uuid, "rssi": rssi}
        arrayOfDevices.append(newDevice)

    print(arrayOfDevices)
    print(f"Found {counter} devices with service UUID: 0000fd85-0000-1000-8000-00805f9b34fb")
    eel.addToLog(str(f"Found {counter} devices with service UUID: 0000fd85-0000-1000-8000-00805f9b34fb"))

def startApp():
    # Initialize and start the Eel app
    eel.init("ui")
    eel.start('index.html', size=(800, 600))

if __name__ == "__main__":
    startApp()