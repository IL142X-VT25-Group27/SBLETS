# Description: Gateway BLE <-> UDP
# Author: Syncore Technologies AB
#
# Version: 1.0 
#
# Based on the work of ble-serial https://github.com/Jakeler/ble-serial
# that use bleak as BLE lib
# -----------------------------------------------------------------

import argparse
import asyncio
import logging
import sys
import time
import traceback
import datetime
import signal
import os
import functools
from webserver import clearDeviceData, getDeviceAlias
from SessionData import sessionData

sys.path.append(os.path.dirname(__file__))

from bleak.exc import BleakError
from ble_interface import BLE_interface
from log.console_log import setup_logger
from log.fs_log import FS_log, Direction
from ports.udp_interface import UDP
import eel


# Debug Callback
def the_callback(text, mac):
    print(mac, text)


class Main:
    def __init__(
            self,
            device,
            addr_type,
            adapter,
            write_uuid,
            read_uuid,
            server_port,
            server_address,
            verbose,
            callbackfunc,
            timeout,
            autoreconnect,
            running,
    ):

        self._autoreconnect = autoreconnect
        self._device = device
        self._addr_type = addr_type
        self._adapter = adapter
        self._write_uuid = write_uuid
        self._read_uuid = read_uuid
        self._server_port = server_port
        self._server_address = server_address
        self._verbose = verbose
        self._callbackfunc = callbackfunc
        self._timeout = timeout
        self._callstop = running

    def start(
            self,
    ):
        try:
            asyncio.run(self._run())
        # KeyboardInterrupt causes bluetooth to disconnect, but still a exception would be printed here
        except KeyboardInterrupt as e:
            logging.debug("Exit due to KeyboardInterrupt")

    async def _run(self):
        self.excpWinrtEvent = asyncio.Event()
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(self.excp_handler)

        # Thread is now used instead of multiprocessing:
        # if sys.platform != 'win32':
        #     logging.debug("No Win32 signal handler set!")
        #     loop.add_signal_handler(signal.SIGTERM, functools.partial(self.ask_exit, signal.SIGTERM))
        # else:
        #     logging.debug("Win32 detected no signal handler set!")

        # UDP
        mtu = 20
        dest_ip = self._server_address
        dest_port = self._server_port

        if dest_ip == "127.0.0.1":
            source_ip = "127.0.0.1"
        else:
            source_ip = "0.0.0.0"

        source_port = 0  # Any Port

        # BLE
        device = self._device
        addr_type = self._addr_type
        adapter = "hci0"
        write_uuid = "98bd0002-0b0e-421a-84e5-ddbf75dc6de4"
        read_uuid = "98bd0003-0b0e-421a-84e5-ddbf75dc6de4"
        filename = datetime.datetime.now().strftime("%Y%m%d-%H%M%S.log")
        filename = None
        binlog = True

        try:
            self.udp = UDP(loop, mtu, dest_ip, dest_port, source_ip, source_port)
            self.bt = BLE_interface()
            if filename:
                self.log = FS_log(filename, binlog)
                self.bt.set_receiver(
                    self.log.middleware(Direction.BLE_IN, self.udp.queue_write)
                )
                self.udp.set_receiver(
                    self.log.middleware(Direction.BLE_OUT, self.bt.queue_send)
                )
            else:
                self.bt.set_receiver(self.udp.queue_write)
                self.udp.set_receiver(self.bt.queue_send)

            self.udp.start()
            await self.bt.start(
                device,
                addr_type,
                adapter,
                write_uuid,
                read_uuid,
                self._timeout,
                self._callbackfunc,
                self._autoreconnect,
                self._callstop,
                self.excpWinrtEvent,
            )
            logging.info("Running main loop!")
            if not self.bt._connected:  # Fix else stuck if cant connect
                logging.error(f"Bluetooth connection failed")
                eel.putRLog(f"gateway.py: Bluetooth connection failed")
                eel.changeConnectStatus("Bluetooth connection failed")  # This is only stored dynamic
                sessionData.connectStatusCode = 4
                clearDeviceData() # If a device was connected clear data
            else:
                self.main_loop = asyncio.gather(self.bt.send_loop(), self.udp.run_loop(), self.monitor_thread())
                await self.main_loop

        except BleakError as e:
            logging.error(f"Bluetooth connection failed: {e}")
            eel.changeConnectStatus("Bluetooth connection failed")
            sessionData.connectStatusCode = 4
            clearDeviceData()  # If a device was connected clear data
        ### KeyboardInterrupts are now received on asyncio.run()
        # except KeyboardInterrupt:
        #     logging.info('Keyboard interrupt received')
        except Exception as e:
            logging.error(f"Unexpected Error: {e}")
            # traceback.print_exc()
        finally:
            logging.warning("Shutdown initiated")
            clearDeviceData()
            # eel.changeConnectStatus("Gateway closed")
            if hasattr(self, "uart"):
                self.udp.remove()
            if hasattr(self, "bt"):
                await self.bt.disconnect()
            if hasattr(self, "log"):
                self.log.finish()
            logging.info("Shutdown complete.")

    def excp_handler(self, loop: asyncio.AbstractEventLoop, context):
        # Handles exception from other tasks (inside bleak disconnect, etc)
        # loop.default_exception_handler(context)
        importantCodes = [5, 6] # Codes to not be overwritten by disconnect functionality

        logging.debug(f'Asyncio exception handler called {context["exception"]}')
        # Different winrt errors that can happen on windows
        if "winrt" in str(context["exception"]) or "Event loop is closed" in str(context["exception"]) or "WinError" in str(context["exception"]):
            # Winrt is unstable
            logging.debug(f'Winrt ERROR detected')
            self.excpWinrtEvent.set()  # This can be used by ble_interface to recognize winrt errors
            # raise Exception("Winrt ERROR")
        # If disconnect in ble_interface.py is not used but disconnected correclty, but the device still disconnected handle that
        elif "disconnected" in str(context["exception"] and sessionData.connectStatusCode not in importantCodes):
            logging.info("Bluetooth disconnected")
            eel.putRLog(f"gateway.py: Bluetooth disconnected")
            eel.changeConnectStatus("Disconnected")
            clearDeviceData()
            sessionData.connectStatusCode = 2
        self.udp.stop_loop()
        self.bt.stop_loop()

    def ask_exit(self, signame):
        logging.warning(f"{signame} Shutdown initiated")
        raise Exception("SIGTERM Shutdown initiated")

    # Makes it possible for the main thread to terminate gateway
    async def monitor_thread(self):
        while not self._callstop.is_set():
            await asyncio.sleep(0.5)
        self.udp.stop_loop()
        self.bt.stop_loop()
        logging.warning(f"SIGTERM or shutdown received, Shutdown initiated")
        eel.putRLog("gateway.py: SIGTERM or shutdown received, Shutdown initiated")
        # raise Exception("SIGTERM received, Shutdown initiated")


def launch(
        device,
        addr_type,
        adapter,
        write_uuid,
        read_uuid,
        server_port,
        server_address,
        verbose: bool,
        callbackfunc,
        time,
        autoreconnect,
        running,
):
    m = Main(
        device,
        addr_type,
        adapter,
        write_uuid,
        read_uuid,
        server_port,
        server_address,
        verbose,
        callbackfunc,
        time,
        autoreconnect,
        running,
    )

    setup_logger(verbose, True)  # Debug ON / OFF
    m.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Create UDP ports from BLE devices.",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Increase verbosity to log all data going through",
    )
    parser.add_argument(
        "-d",
        "--dev",
        dest="device",
        required=True,
        help="BLE device address to connect (hex format, can be seperated by colons)",
    )
    parser.add_argument(
        "-t",
        "--address-type",
        dest="addr_type",
        required=False,
        choices=["public", "random"],
        default="public",
        help="BLE address type, either public or random",
    )
    parser.add_argument(
        "-i",
        "--interface",
        dest="adapter",
        required=False,
        default="hci0",
        help="BLE host adapter number to use",
    )
    parser.add_argument(
        "-m",
        "--mtu",
        dest="mtu",
        required=False,
        default=20,
        type=int,
        help="Max. bluetooth packet data size in bytes used for sending",
    )
    parser.add_argument(
        "-w",
        "--write-uuid",
        dest="write_uuid",
        required=False,
        help='The GATT characteristic to write the serial data, you might use "ble-scan -d" to find it out',
    )
    parser.add_argument(
        "-l",
        "--log",
        dest="filename",
        required=False,
        help="Enable optional logging of all bluetooth traffic to file",
    )
    parser.add_argument(
        "-b",
        "--binary",
        dest="binlog",
        required=False,
        action="store_true",
        help="Log data as raw binary, disable transformation to hex. Works only in combination with -l",
    )
    parser.add_argument(
        "-p",
        "--port",
        dest="port",
        required=False,
        default=5684,
        help="The port of the server, 5684 or 5683",
    )
    parser.add_argument(
        "-a",
        "--address",
        dest="address",
        required=False,
        default="127.0.0.1",
        help="The address of the server",
    )
    parser.add_argument(
        "-r",
        "--read-uuid",
        dest="read_uuid",
        required=False,
        help="The GATT characteristic to subscribe to notifications to read the serial data",
    )

    args = parser.parse_args()

    launch(
        args.device,
        args.addr_type,
        args.adapter,
        args.write_uuid,
        args.read_uuid,
        args.port,
        args.address,
        args.verbose,
        the_callback,
        None,
    )
