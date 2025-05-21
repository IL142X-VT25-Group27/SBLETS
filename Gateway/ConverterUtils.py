# Description: Convert Functions
# Author: Syncore Technologies AB
#
# -----------------------------------------------------------------


# Const
LWM2M_MESSAGE_MAX_SIZE = 1152
HQV_LINKED_LAYER_MESSAGE_TYPE = 0x01
HQV_LINKED_LAYER_MESSAGE_MAX_SIZE = LWM2M_MESSAGE_MAX_SIZE + 4
HQV_LINKED_LAYER_MESSAGE_MIN_SIZE = 4
DTLS = 1
UNENCRYPTED = 0
REMOTE = 1
LOCAL = 0


def IsPacketHeaderValid(packetHeader):
    return 0 <= packetHeader < 4  # packetHeader >= 0 and packetHeader < 4


def GetServerType(packetHeader):
    # 1 for REMOTE and 0 for LOCAL
    return REMOTE if ((packetHeader & 1) == 1) else LOCAL


def GetTransportSecurity(packetHeader):
    # 1 for DTLS and 0 for UNENCRYPTED
    return DTLS if ((packetHeader & 2) == 2) else UNENCRYPTED


def ToPacketHeader(serverType, transportSecurity):

    if serverType == REMOTE:
        return 3 if (transportSecurity == DTLS) else 1

    if serverType == LOCAL:
        return 2 if (transportSecurity == DTLS) else 0

    # TODO: Exeption raise
