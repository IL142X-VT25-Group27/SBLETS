# simulate_imc.py
from datetime import datetime
import os
import time
import logging
import eel
from IMC_Simulator.IMC_Simulator.IMC_Simulator import *
from IMC_Simulator.IMC_Simulator.Stopwatch import Stopwatch

logger = logging.getLogger(__name__)

def InitLogger():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    if not os.path.exists('simlog'):
        os.mkdir('simlog')
    file_handler = logging.FileHandler(f"simlog/logger_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    file_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(message)s'))
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s: %(message)s'))
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

def Log(simData: SimData, returnData: ReturnData):
    logger.info(f"control: {simData.control.name}, revspeed: {simData.revspeed}, index_pulsewidth: {simData.index_pulsewidth}, accumulated_time: {returnData.accumulated_time.value}")
    put_log(f"control: {simData.control.name}, revspeed: {simData.revspeed}, index_pulsewidth: {simData.index_pulsewidth}, accumulated_time: {returnData.accumulated_time.value}")

def Wait(t):
    stopwatch = Stopwatch()
    stopwatch.start()
    while stopwatch.duration < t:
        time.sleep(0.01)
    stopwatch.stop()

def runSimSingleRevspeed(freq: int):
    InitLogger()
    msg = f"Single revspeed {freq} Hz simulation started..."
    logger.info(msg)
    put_log(msg)

    simData = SimData(revspeed=freq, index_pulsewidth=325, control=ControlEnum.reset, messages=[])
    simulator = IMC_Simulator("STLink")

    simData.control = ControlEnum.reset
    Wait(10)
    simulator.SendData(simData)

    # Send start command with correct revspeed
    simData.control = ControlEnum.start
    simData.revspeed = freq
    simData.index_pulsewidth = 325
    result = simulator.SendData(simData)
    Log(simData, result)

    Wait(8)

    simData.control = ControlEnum.stop
    result = simulator.SendData(simData)

    done_msg = f"Single revspeed {freq} Hz simulation finished..."
    logger.info(done_msg)
    put_log(done_msg)

def runSimRev50(): runSimSingleRevspeed(50)
def runSimRev150(): runSimSingleRevspeed(150)
def runSimRev250(): runSimSingleRevspeed(250)

def runSimHighAndLow():
    InitLogger()
    logger.info("Multiple revspeed (High and Low) simulation started...")
    put_log("Multiple revspeed (High and Low) simulation started...")
    
    simData = SimData(revspeed=25, index_pulsewidth=325, control=ControlEnum.reset, messages=[])
    simulator = IMC_Simulator("STLink")

    simData.control= ControlEnum.reset
    Wait(10)
    result = simulator.SendData(simData)          

    start = 40
    stop = 240
    step = (100/60)*5

    #Low to high
    simData.control = ControlEnum.start
    simData.index_pulsewidth = 325
    revspeed = start
    while revspeed <= 90:
        simData.revspeed = revspeed
        result = simulator.SendData(simData)
        Log(simData, result)
        Wait(10)
        revspeed += step

    revspeed = 190
    while revspeed <= 241:
        simData.revspeed = revspeed
        result = simulator.SendData(simData)
        Log(simData, result)
        Wait(10)
        revspeed += step

    simData.control= ControlEnum.stop
    result = simulator.SendData(simData)                       

    logger.info("Multiple revspeed (High and Low) simulation finished...")
    put_log("Multiple revspeed (High and Low) simulation finished...")
       
    
def runSimLong(): 
    InitLogger()
    logger.info("All revspeed simulation started...")
    put_log("All revspeed simulation started...")
    
    simData = SimData(revspeed=25, index_pulsewidth=325, control=ControlEnum.reset, messages=[])
    simulator = IMC_Simulator("STLink")

    simData.control= ControlEnum.reset
    Wait(10)
    result = simulator.SendData(simData)          

    #All Hz 0 to 300
    start = 0
    stop = 300
    step = 100/60

    simData.control = ControlEnum.start
    simData.index_pulsewidth = 325
    revspeed = start
    while revspeed <= 300:
        simData.revspeed = revspeed
        result = simulator.SendData(simData)
        Log(simData, result)
        Wait(8)
        revspeed += step
    simData.control= ControlEnum.stop
    result = simulator.SendData(simData)  
    logger.info("All revspeed simulation finished...")
    put_log("All revspeed simulation finished...")

def put_log(msg):
    try:
        eel.putSimLog(msg)  # sends to frontend
    except Exception as e:
        print(f"Failed to send log to frontend: {e}")