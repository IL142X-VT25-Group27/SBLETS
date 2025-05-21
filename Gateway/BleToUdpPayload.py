# Description: BLE To UDP Payload
# Author: Syncore Technologies AB
#
# Changes made to GetNextUdpMessage to handle multiple messages in a packet (new advertisement structure
# for newer ble modules). - Alexander Ström 2024-06-19
# -----------------------------------------------------------------

import struct
import logging
import ConverterUtils


class BleToUdpPayload:
    def __init__(self):
        self.messageBuffer = bytearray()
        self.packetHeader = -1
        self.packetSize = -1
        self.packetType = -1

    def __del__(self):
        pass
        # logging.info("Destructor called, BleToUdpPayload")

    def Create(self, data=bytearray()):
        self.messageBuffer = data
        self.ResetHeaders()

    def CanBufferContainAllHeaders(self):
        return (
                len(self.messageBuffer) >= ConverterUtils.HQV_LINKED_LAYER_MESSAGE_MIN_SIZE
        )

    def NoInitializedHeaders(self):
        return not ((self.packetHeader != -1) and (self.packetSize != -1))

    def GetPacketHeader(self):
        if not self.CanBufferContainAllHeaders():
            return -1
        return self.messageBuffer[3]

    def GetPacketType(self):
        if not self.CanBufferContainAllHeaders():
            return -1
        return self.messageBuffer[0]

    def GetPacketSize(self):
        if not self.CanBufferContainAllHeaders():
            return -1
        return struct.unpack("!H", self.messageBuffer[1:3])[0]

    def IsPacketTypeValid(self, packetType):
        return packetType == ConverterUtils.HQV_LINKED_LAYER_MESSAGE_TYPE

    def IsPacketHeaderValid(self, packetHeader):
        return ConverterUtils.IsPacketHeaderValid(packetHeader)

    def IsPacketSizeValid(self, packetSize):
        return (packetSize > 0) and (
                (packetSize + 3) <= ConverterUtils.HQV_LINKED_LAYER_MESSAGE_MAX_SIZE
        )

    def TryInitializeHeaders(self):
        self.packetHeader = self.GetPacketHeader()
        self.packetSize = self.GetPacketSize()
        self.packetType = self.GetPacketType()

        if (
                self.IsPacketTypeValid(self.packetType)
                and self.IsPacketHeaderValid(self.packetHeader)
        ) and self.IsPacketSizeValid(self.packetSize):
            # logging.debug(f"TryInitializeHeaders: True")
            return True
        else:
            logging.debug(f"TryInitializeHeaders: False")
            return False

    def HasCompleteMessageInBuffer(self):
        return len(self.messageBuffer) >= (self.packetSize + 3)

    def GetNextUdpMessage(self):
        udpMessage = bytearray()
        udpMessageFull = bytearray(self.messageBuffer[4:])

        # More than one message in buffer (Makes sure every message in one packet is sent to server)
        if len(self.messageBuffer) > (self.packetSize + 3):
            logging.debug(f"Complete message: {udpMessageFull}")
            logging.debug(f"More data in buffer!")
            udpMessage = bytearray(self.messageBuffer[4: (self.packetSize + 3)])
            msg_left = self.messageBuffer[(self.packetSize + 3):]
            self.Create(bytearray())
            self.Create(msg_left)
            udpMessageBuffer = bytearray(self.messageBuffer[4:])
            logging.debug(f"In buffer message: {udpMessageBuffer}")  # commonly three combined messages to be split
            return udpMessage
        else:
            udpMessage = bytearray(self.messageBuffer[4:])
            logging.debug(f"Handling main message: {udpMessage}")
            self.Create(bytearray())
        return udpMessage

    def ResetHeaders(self):
        self.packetSize = -1
        self.packetHeader = -1

    def Convert(self, blemessage):
        self.messageBuffer.extend(blemessage)

        if not self.CanBufferContainAllHeaders():
            logging.debug(f"CanBufferContainAllHeaders False")
            self.Create(bytearray())
            return None
        if self.NoInitializedHeaders():
            if not self.TryInitializeHeaders():
                self.Create(bytearray())
                return None

        if self.HasCompleteMessageInBuffer():
            logging.debug(f"HasCompleteMessageInBuffer")
            packetHeader = self.packetHeader
            return (self.GetNextUdpMessage(), packetHeader)
        return None
