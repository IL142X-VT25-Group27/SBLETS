# Description: UDP Interface
# Author: Syncore Technologies AB
#
# -----------------------------------------------------------------
import eel
from ports.interface import ISerial
import asyncio
import logging
import socket
import UdpToBlePayload


class UDP(ISerial):
    def __init__(
        self,
        ev_loop: asyncio.AbstractEventLoop,
        mtu: int,
        dest_ip: str,
        dest_port: int,
        source_ip: str,
        source_port: int,
    ):
        self.loop = ev_loop
        self.mtu = 23  # (mtu + 3) FG
        self._send_queue = asyncio.Queue()

        self._send_to_address = (dest_ip, int(dest_port))
        address = (source_ip, int(source_port))

        # Create socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)

        sock.bind(address)

        self._socket = sock

        logging.info(f"UDP socket bind to {sock.getsockname()}")
        logging.info(f"UDP socket sends data to {self._send_to_address}")

    def set_receiver(self, callback):
        self._cb = callback

    def start(self):
        assert self._cb, "Receiver must be set before start!"

        # Register the file descriptor for read event
        self.loop.add_reader(self._socket.fileno(), self.read_handler)

    def stop_loop(self):
        logging.info("Stopping UDP event loop")
        self._send_queue.put_nowait(None)

    def remove(self):
        # Unregister the fd
        self.loop.remove_reader(self._socket)
        logging.info(f"UDP reader removed")

    def read_handler(self):

        udpmessage = self.read_sync()
        logging.debug(f"Received UDP: ({len(udpmessage)}) {udpmessage}")
        eel.putRLog(f"udp_interface.py: Received UDP: ({len(udpmessage)})")

        udptoble = UdpToBlePayload.UdpToBlePayload(self.mtu)  # MTU Size 23
        # header = ConverterUtils.ToPacketHeader(ConverterUtils.REMOTE, ConverterUtils.DTLS) # FG
        header = 3  # Header Remote and DTLS
        blemessages = udptoble.Convert(udpmessage, header)

        logging.debug("Send split BLE messages")
        for msg in blemessages:
            self._cb(msg)

    def read_sync(self):
        value, address = self._socket.recvfrom(1024)
        # logging.debug(f'Read: {value}')
        return value

    def queue_write(self, value: bytes):
        self._send_queue.put_nowait(value)

    async def run_loop(self):
        while True:
            data = await self._send_queue.get()
            if data == None:
                logging.debug(f"UDP Loop Break")
                break  # Let future end on shutdown
            length = len(data)
            logging.debug(f"Write UDP: ({length}) {data}")
            eel.putRLog(f"udp_interface.py: Write UDP: ({length})")
            retries = 0
            while retries < 3:
                sent = self._socket.sendto(data, self._send_to_address)
                logging.debug(f"Sent UDP: {sent}")
                if sent == length:
                    break
                else:
                    retries = retries + 1

            if retries == 3:
                logging.warning(f"Could not send {data} over gateway UDP socket")
                # TODO: How to handle this?
                # Disconnect(); #Leftovers from C# application
