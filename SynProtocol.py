# Description: Converter for Syncore Protocol
# Author: Syncore Technologies AB
#
# -----------------------------------------------------------------

# Const
ETX = 0x03
STX = 0x02
ESC = 0x1B
ESC_STX = 0x82
ESC_ETX = 0x83
ESC_ESC = 0x9B


def decode_data(data):
    data_out = bytearray()
    jump_next = False

    for index, d in enumerate(data):

        if d != ESC:
            if not (d == STX or d == ETX):
                if not jump_next:
                    data_out.append(d)
                jump_next = False
        elif (d == ESC) and (data[index + 1] == ESC_STX):
            data_out.append(STX)
            jump_next = True

        elif (d == ESC) and (data[index + 1] == ESC_ETX):
            data_out.append(ETX)
            jump_next = True

        elif (d == ESC) and (data[index + 1] == ESC_ESC):
            data_out.append(ESC)
            jump_next = True

    return data_out


def encode_data(data):
    data_out = bytearray()

    # Add Start Byte
    data_out.append(STX)

    for src in data:

        if src == STX:
            data_out.append(ESC)
            data_out.append(ESC_STX)

        elif src == ETX:
            data_out.append(ESC)
            data_out.append(ESC_ETX)

        elif src == ESC:
            data_out.append(ESC)
            data_out.append(ESC_ESC)

        else:
            data_out.append(src)

    # Add end byte
    data_out.append(ETX)

    return data_out
