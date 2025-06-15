# from dataclasses import asdict, dataclass
import serial
import json
import serial.tools.list_ports
from typing import List
from serial.tools.list_ports_common import ListPortInfo
from typing import Optional
import logging
from ctypes import c_uint64
from .Config import *

logger = logging.getLogger(__name__)


class IMC_Simulator:

    def __init__(self, serial_number: str):
        self.current_port = self.get_port_by_serial_number(serial_number)
        logger.debug(f"Serial port: {self.current_port}")
    
    @staticmethod
    def port_to_string(port: ListPortInfo) -> str:
        return f"{port.device}, {port.description}, {port.serial_number}, VID-HID: {port.vid}-{port.pid}"
    
    @staticmethod
    def list_serial_ports():

        ports = serial.tools.list_ports.comports()

        if not ports:
            print("No serial ports found.")
            return

        print("Available Serial Ports:")
        for port in ports:
            print(f"{IMC_Simulator.port_to_string(port)}")

    def get_port_by_serial_number(self, serial_number: str) -> Optional[str]:
        ports: List[ListPortInfo] = serial.tools.list_ports.comports()
        hit_ports: List[ListPortInfo] = []

        for port in ports:
            description = self.port_to_string(port)
            if serial_number in description:
                hit_ports.append(port)

        if len(hit_ports) == 0:
            logger.error(f"No serial port found for {serial_number}.")
        elif len(hit_ports) == 1:
            return hit_ports[0].device
        else:
            logger.error(
                f"Duplicate serial ports found for {serial_number}. Only one is expected.")

        return None

    def SendData(self, simData: SimData) -> ReturnData:
        try:
            # Default response in case of failure
            default_return_data = ReturnData(
                status="error", accumulated_time=c_uint64(0))

            # Serialize the Config object to JSON
            json_data = ConfigSerializer.serialize(simData) + "\n"
            json_str = json_data.replace(" ", "").replace("\n", "") + "\n"

            with serial.Serial(self.current_port, 115200, timeout=1) as ser:
                # Send the JSON string
                ser.write(json_str.encode('utf-8'))
                logger.debug(f"Sent: \n{json_str}")

                # Read the response from the serial port
                received_data = ser.read_until()
                if received_data:
                    try:
                        # Parse the received JSON
                        received_json = json.loads(
                            received_data.decode('utf-8'))
                        logger.debug(
                            f"Received: {json.dumps(received_json, indent=4)}")

                        # Map the received JSON to the ReturnData dataclass
                        return ReturnData(
                            status=received_json.get("status", "error"),
                            accumulated_time=c_uint64(
                                received_json.get("accumulated_time", 0))
                        )
                    except json.JSONDecodeError:
                        logger.error(
                            f"Received non-JSON data: {received_data.decode('utf-8')}")
                else:
                    logger.error("No response received.")
            return default_return_data

        except serial.SerialException as e:
            logger.error(f"Serial error: {e}")
            return ReturnData(status="serial_error", accumulated_time=c_uint64(0))
        except Exception as e:
            logger.error(f"Error: {e}")
            return ReturnData(status="general_error", accumulated_time=c_uint64(0))
