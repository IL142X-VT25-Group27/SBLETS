# Description: UDP to BLE Payload
# Author: Syncore Technologies AB
#
# -----------------------------------------------------------------

import ConverterUtils
import struct
import logging


class UdpToBlePayload:
    def __init__(self, mtu):
        self._mtu = mtu

    def __del__(self):
        pass
        # logging.info("Destructor called, UdpToBlePayload")

    def Convert(self, payload, PacketHeader):

        if (
            payload is None
            and PacketHeader is None
            and (not (len(payload) <= ConverterUtils.HQV_LINKED_LAYER_MESSAGE_MAX_SIZE))
        ):
            logging.warning(f"Fail in Convert Function")
            return None

        bleMessage = self.CreateBleMessage(payload, PacketHeader)
        return self.SplitBleMessage(bleMessage)

    def CreateBleMessage(self, udpMessage, packetHeader):

        bleMessage = bytearray()
        bleMessage.append(ConverterUtils.HQV_LINKED_LAYER_MESSAGE_TYPE)

        lengthValue = len(udpMessage) + 1  # package header included in length value

        messagesize = struct.pack("!H", lengthValue)

        bleMessage.extend(messagesize)

        # logging.debug(f"Size of UDP message: {len(udpMessage)}")

        bleMessage.append(packetHeader)
        bleMessage.extend(udpMessage)

        return bleMessage

    def SplitBleMessage(self, bleMessage):

        bleMessageList = []

        bleMessageIndex = 0
        payloadSize = self._mtu - 3
        while bleMessageIndex < len(bleMessage):
            partialBleMessageSize = min(
                payloadSize, (len(bleMessage) - bleMessageIndex)
            )
            # logging.debug(f"partialBleMessageSize: {partialBleMessageSize}")

            partialBleMessage = bytearray(
                bleMessage[bleMessageIndex : (bleMessageIndex + partialBleMessageSize)]
            )
            # logging.debug(f"Size of partialBleMessage: {len(partialBleMessage)}")
            bleMessageIndex = bleMessageIndex + partialBleMessageSize

            bleMessageList.append(partialBleMessage)

        return bleMessageList
