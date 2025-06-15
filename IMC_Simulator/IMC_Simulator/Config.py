import json
from dataclasses import asdict, dataclass
from typing import List
from ctypes import c_uint64
from enum import Enum
CONFIG_VERSION = 4

class ControlEnum(Enum):
    start = 1
    stop = 2
    reset = 3

@dataclass
class Message:
    message_delay: int
    baudrate: int
    data_bits: int
    parity_bit: str
    stop_bits: int
    data: List[int]


@dataclass
class SimData:
  
    revspeed: int
    index_pulsewidth: int
    control: ControlEnum    
    messages: List[Message]
    
    def __post_init__(self):
        # Ensure the version is always the constant value
        object.__setattr__(self, 'VERSION', SimData.version)
    version: int = CONFIG_VERSION  # Class-level constant


@dataclass
class ReturnData:
    status: str
    accumulated_time: c_uint64


class ConfigSerializer:
    @staticmethod
    def deserialize(json_str: str) -> SimData:
        data = json.loads(json_str)

        # Deserialize nested structures
        messages = [
            Message(
                message_delay=msg["message_delay"],
                baudrate=msg["baudrate"],
                data_bits=msg["data_bits"],
                parity_bit=msg["parity_bit"],
                stop_bits=msg["stop_bits"],
                data = msg["data"]
            )
            for msg in data["messages"]
        ]

        # Return the Config object
        return SimData(
            revspeed=data["revspeed"],
            index_pulsewidth=data["index_pulsewidth"],
            messages=messages,
            control= data["control"]
        )

    @staticmethod    
    def serialize(simData: SimData) -> str:
        # Convert the dataclass to a dictionary
        data = asdict(simData)

        # Convert control enum to its name for JSON serialization
        data["control"] = simData.control.name

        # Serialize to JSON
        return json.dumps(data, indent=2)
    
    # def serialize(simData: SimData) -> str:
    #     # Convert the dataclass to a dictionary and serialize it to JSON
    #     data = asdict(simData)
    #     return json.dumps(data, indent=2)

    @staticmethod
    def SaveToFile(simData: SimData, filename: str) -> None:
        with open(filename, 'w') as file:
            json_str = ConfigSerializer.serialize(simData)
            file.write(json_str)

    @staticmethod
    def LoadFromFile(filename: str) -> SimData:
        with open(filename, 'r') as file:
            json_str = file.read()
            return ConfigSerializer.deserialize(json_str)
            

