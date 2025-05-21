# Description: BLE Test Handler
# Author: Syncore Technologies AB
#
# -----------------------------------------------------------------
import asyncio

from bleak import BleakClient, BleakScanner  # Bleak Lib
import bluetoothctl_wrapper  # Wrapper for Bluetoothctl

import time
import os
import logging

# TODO: Make a class intead?
# class SynBlue()


from enum import Enum, unique


@unique
class Return_type(Enum):
    SUCCESS = 0
    FAIL = 1
    ERROR = 2


# Interface


def List_Of_Devices_Test(timeout: int):
    logging.debug("Run List Of Devices")
    # Remove old device first
    Clean_Devices()

    device_list = []

    from bluepy.btle import Scanner

    devices = Scanner().scan(timeout)
    COMPLETE_LOCAL_NAME_ADTYPE = 9
    for dev in devices:

        name = dev.getValueText(COMPLETE_LOCAL_NAME_ADTYPE)

        # If None change to addr
        if name is None:
            name = dev.addr

        device_list.append({"mac_address": dev.addr, "name": name})

        # logging.debug(dev.addr)

    return device_list


def Connect_And_Wait_For_Disconnect_Test(mac_addr, _callback, timeout):
    import asyncio

    logging.debug("Run Connect_And_Wait_For_Disconnect_Test")
    asyncio.run(show_disconnect_handling(mac_addr, _callback, timeout))
    logging.debug("Done Connect_And_Wait_For_Disconnect")
    return None


def Disconnect_Test(mac_addr):
    logging.debug("Run Disconnect")
    bl = bluetoothctl_wrapper.Bluetoothctl()
    try:
        bl.disconnect(mac_addr)
    except:
        pass
    finally:
        a = bl.get_device_info(mac_addr)
        matches = [x for x in a if "\tConnected:" in x]
        logging.debug(matches)
        if matches:
            if "no" in matches[0]:
                logging.debug("Return: Disconnected")
                return Return_type.SUCCESS
            else:
                logging.debug("Return: Not Disconnected")
                return Return_type.FAIL
        else:
            logging.debug("Return: Error")
            return Return_type.ERROR


def Advertisement_Period_Test(timer, mac_address):
    mac_address = mac_address.lower()
    time_list = []
    exit_time = time.time() + timer

    async def scan():
        def detection_callback(device, advertisement_data):
            if time.time() > exit_time:
                return

            if device.address.lower() == mac_address:
                time_list.append(time.time_ns())
                logging.debug(f"Detected device {mac_address} at {time.time_ns()}")

        scanner = BleakScanner()
        scanner.register_detection_callback(detection_callback)

        await scanner.start()
        logging.debug(f"Run for {timer} sec")

        try:
            while time.time() < exit_time:
                await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"Error during scanning: {e}")
        finally:
            await scanner.stop()
            logging.debug("Finally closing scanner")

            for i in range(3, len(time_list)):
                ms = (time_list[i] - time_list[i - 1]) / 1000000
                logging.debug(int(ms))

            return time_list

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(scan())
    loop.close()
    return result

def Get_Advertisement_Data_Test(mac, time=30):
    from bluepy.btle import Scanner

    mac_addr = mac.lower()
    devices = Scanner().scan(time)

    for dev in devices:
        if mac_addr in dev.addr:
            logging.debug(f"Device {dev.addr} {dev.addrType} RSSI= {dev.rssi} dB")
            advertisement_data = bytearray()
            for (adtype, desc, value) in dev.getScanData():
                # print("%s: %s = %s" % (adtype, desc, value))
                logging.debug(f"{adtype} {desc} {value}")
                B = bytearray()

                B.extend(
                    int(adtype).to_bytes(1, byteorder="big", signed=False)
                )  # Ad Type

                res_str = value.replace("-", "")
                C = bytearray.fromhex(res_str)
                B.extend(C)
                ad_len = (len(C) + 1).to_bytes(1, byteorder="big", signed=False)

                # if adtype == 0x01:
                # C = bytearray.fromhex(value)
                # #print(len(C))
                # B.extend(C)
                # #B.extend(int(value).to_bytes(1, byteorder='big', signed=False)) # Ad Data
                # #ad_len = (len(B)).to_bytes(1, byteorder='big', signed=False)
                # ad_len = (len(C)+1).to_bytes(1, byteorder='big', signed=False)

                # elif adtype == 0x07:

                # res_str = value.replace('-', '')
                # C = bytearray.fromhex(res_str)
                # B.extend(C)
                # ad_len = (len(C)+1).to_bytes(1, byteorder='big', signed=False)

                # #B.extend(int(value).to_bytes(1, byteorder='big', signed=False)) # Ad Data
                # #ad_len = (len(B)).to_bytes(1, byteorder='big', signed=False)

                # elif adtype == 0xFF:
                # C = bytearray.fromhex(value)

                # B.extend(C)

                # ad_len = (len(C)+1).to_bytes(1, byteorder='big', signed=False)

                # bytearray.fromhex(hex_string)
                # C = bytearray(value)
                # print(len(C))

                advertisement_data.extend(ad_len)
                advertisement_data.extend(B)

            logging.debug(advertisement_data)
            return advertisement_data

    return None


def Get_Need_To_Connect_Test(mac, time=45):

    # START TODO: Bryt ut
    from bluepy.btle import Scanner

    mac_addr = mac.lower()
    devices = Scanner().scan(time)

    for dev in devices:
        if mac_addr in dev.addr:
            # return dev
            # END

            data = dev.getScanData()

            if data:
                for (adtype, desc, value) in data:
                    if adtype == 255:
                        byte_data = bytearray.fromhex(value)
                        # logging.debug(f'{byte_data[22:23]}')
                        # TODO: FG! Extract fields from data by using a class intead
                        logging.debug(
                            f'{hex(int.from_bytes(byte_data[4:20], byteorder="little", signed=False))}'
                        )
                        logging.debug(
                            f'NTC: {(int.from_bytes(byte_data[22:23], byteorder="little", signed=False) & 0b00000001)}'
                        )
                        logging.debug(
                            f'Firmware Down: {(int.from_bytes(byte_data[22:23], byteorder="little", signed=False) & 0b00000010)}'
                        )
                        logging.debug(
                            f'Firmware Run: {(int.from_bytes(byte_data[22:23], byteorder="little", signed=False) & 0b00000100)}'
                        )

                        return (
                            int.from_bytes(
                                byte_data[22:23], byteorder="little", signed=False
                            )
                            & 0b00000001
                        )
            # No data found
            else:
                return -1
    # The right device was not found
    return -1

    # Local functions


async def show_disconnect_handling(mac_addr, _callback, timeout):
    import asyncio

    # devs = await BleakScanner.discover()
    # print(devs)
    start = time.time()
    device = await BleakScanner.find_device_by_address(mac_addr, timeout)
    end = time.time()
    logging.debug(f"{end - start}")
    logging.debug(device)

    if device is None:
        logging.debug("No devices found, try again later.")
        _callback("Connected: NO", mac_addr)
        return None
    disconnected_event = asyncio.Event()

    def disconnected_callback(client):
        logging.debug("Disconnected callback called!")
        disconnected_event.set()

    # Try to connect for 60 sec max (The device has been spoted in prev part of code so
    endtime = time.time() + 60

    while endtime > time.time():

        try:

            async with BleakClient(
                mac_addr, disconnected_callback=disconnected_callback
            ) as client:
                _callback("Connected: YES", mac_addr)
                logging.debug("Sleeping until device disconnects...")
                await disconnected_event.wait()
                # print("Connected: {0}".format(await client.is_connected()))
                _callback("Disconnected", mac_addr)
                await asyncio.sleep(
                    1
                )  # Sleep a bit longer to allow _cleanup to remove all BlueZ notifications nicely...
                return 1
        # TODO: Handel correct Exception
        except Exception as e:
            logging.debug(f"{e}")
            pass

    # Error instead?
    _callback("Connected: NO", mac_addr)
    return None


def Clean_Devices():
    logging.debug(Clean_Devices.__name__)
    bl = bluetoothctl_wrapper.Bluetoothctl()

    for dev in bl.get_discoverable_devices():
        # print(dev['mac_address'])
        bl.remove(dev["mac_address"])
        time.sleep(0.1)


def Fast_Scan(time_sec):
    logging.debug(Fast_Scan.__name__)
    bl = bluetoothctl_wrapper.Bluetoothctl()
    bl.start_scan()
    time.sleep(time_sec)
    bl.stop_scan()


async def Scan_For_Device_2(mac, time_sec):
    logging.debug(Scan_For_Device_2.__name__)

    await BleakScanner.discover()

    device = await BleakScanner.find_device_by_address(mac)
    logging.debug(device)

    if device is None:
        logging.debug("No devices found, try again later.")
        return 0
    else:
        return 1


def Scan_For_Device_Test(mac, time_sec):
    logging.debug(Scan_For_Device.__name__)

    # Clear Devices
    Clean_Devices()

    bl = bluetoothctl_wrapper.Bluetoothctl()

    # print(bl.get_discoverable_devices()) #List of Dic [mac_address , name]

    bl.start_scan()
    # Scan for 10 sec
    for i in range(0, time_sec):
        time.sleep(1)

    bl.stop_scan()
    for dev in bl.get_discoverable_devices():
        if mac in dev["mac_address"]:
            return True

    logging.debug("No devices found, try again later.")
    return None


def Get_Manufacturer_Data_Test(mac_addr):
    import asyncio as a

    result = a.run(Get_Manufacturer_Data(mac_addr))

    return result


async def Get_Manufacturer_Data(mac_addr):
    COMPANY_CODE = 0x0426

    logging.debug(Get_Manufacturer_Data.__name__)
    devices = await BleakScanner.discover()
    for d in devices:
        if mac_addr in d.address:
            # Return manufacturer data for COMPANY_CODE as a bytearray (COMPANY_CODE not included)
            return bytearray(d.metadata["manufacturer_data"][COMPANY_CODE])

    return None


if __name__ == "__main__":
    pass
