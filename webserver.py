############################################### --- SBLETS Webserver --- ###############################################

# Alexander Ström 2024-07-04
# This webserver file contains links to multiple components that hosts services on the local webserver used for
# controlling SBLETS
# To show a log message on the GUI use eel.putRLog(msg)

########################################################################################################################

from tools.generateOmaDdf import *
from tools.addDeviceData import *
import json
import sys
import ctypes
from json import JSONDecodeError
import eel
from SessionData import sessionData

# Version of SBLETS
version = "1.5.4"

# If app or webapp
guiType = ""

# Initial states for sub services status
serverStatus = "Dead"
tcpStatus = "Dead"
websocketStatus = "Dead"
webserverStatus = "Dead"

statusKeys = {
    "server": "serverStatus",
    "tcp": "tcpStatus",
    "websocket": "websocketStatus",
    "webserver": "webserverStatus"  # Sets ready from main.js
}

# Create a ConfigParser object
config = configparser.ConfigParser()

# Read the configuration file
config.read('config.ini')

def getSbletsVersion():
    global version
    return version

# Only used by frontend as it cannot access global session data class
@eel.expose
def getSessionData(key=None):
    if key is None:
        return
    else:
        return getattr(sessionData, key)


# A method to clear all device data instead of doing manual writes
def clearDeviceData():
    sessionData.connectedDeviceMac = None
    sessionData.connectedDeviceHID = None
    sessionData.connectedDeviceIPRID = None
    sessionData.uniqueSessionUUID = sessionData.startupUniqueSessionUUID
    eel.pingFrontend()


# This is the status for SBLETS not webserver (Its here because only the webserver GUI wants to know the state)
@eel.expose
def getStatus(service):
    try:
        return globals()[statusKeys[service]]
    except KeyError:
        logging.warning(f"Unknown service: {service}")


# Set new status for sub service
@eel.expose
def setStatus(status, service):
    try:
        globals()[statusKeys[service]] = status
    except KeyError:
        logging.warning(f"Unknown service: {service}")
    if globals()[statusKeys["webserver"]] == "Ready":
        eel.pingFrontend()


# Check if alias exist to the device
def getDeviceAlias(uuid):
    deviceLookupFilePath = (config.get('SBLETS', 'Device lookup path'))
    if deviceLookupFilePath is None:
        logging.warning(f"No lookup file specified in config!")
        return False

    try:
        with open(deviceLookupFilePath) as jsonData:
            try:
                deviceLookupJSON = json.load(jsonData)
                for jUuid, jAlias in deviceLookupJSON.items():
                    if jUuid == uuid:
                        sessionData.connectedDeviceAlias = jAlias
                        jsonData.seek(0)
                        return jAlias
                jsonData.seek(0)
            except JSONDecodeError:
                pass
    except FileNotFoundError as e:
        logging.warning(e)
        return False
    return "unknown"


# Return the stored secret key for the connected BLE device
def getDeviceKey(uuid):
    deviceSecretsFilePath = (config.get('SBLETS', 'Device secrets path'))
    if deviceSecretsFilePath is None:
        logging.warning(f"No secrets file specified in config!")
        return False

    try:
        with open(deviceSecretsFilePath) as jsonData:
            try:
                deviceSecretsSON = json.load(jsonData)
                for jUuid, jSecret in deviceSecretsSON.items():
                    if jUuid == uuid:
                        jsonData.seek(0)
                        return jSecret
                jsonData.seek(0)
            except JSONDecodeError:
                pass
    except FileNotFoundError as e:
        logging.warning(e)
        return False
    return "unknown"


# JavaScript uses this to fetch information from config.ini and other session data
@eel.expose
def readData():
    statusServer = getStatus("server")
    statusTcp = getStatus("tcp")
    statusWebsocket = getStatus("websocket")

    uuid = sessionData.uniqueSessionUUID
    endpointActive = sessionData.deviceConnectedToLeshan

    customName = config.get("SBLETS", "Name")
    lanip = config.get("SBLETS", "LANIP")
    leshanip = config.get("LESHAN", "IP")
    leshanPort = config.get("LESHAN", "Port")
    webserverPort = config.get("SBLETS", "Webserver port")
    tcpPort = config.get("TCP", "Port")
    websocketPort = config.get("WEBSOCKET", "Port")
    sendStatusRequest = config.get("SBLETS", "Send regularly status request")

    webappAccessValue = config.get("SBLETS", "Allow web app access others")
    if webappAccessValue == "True":
        webappAccess = "Public"
    else:
        webappAccess = "Private"

    # For some reason, this keeps on throwing error but nothing else
    try:
        hid = sessionData.connectedDeviceHID
    except JSONDecodeError:
        pass

    deviceAlias = sessionData.connectedDeviceAlias

    runningGateway = "Active" if sessionData.runningGateway is True else "Inactive"

    if sys.platform == "win32":
        autoReconnect = "Not available on Windows"
    else:
        autoReconnect = "On" if config.get("BLE", "Auto reconnect") is True else "Off"

    return {"Custom name": customName, "Unique session UUID": uuid, "SBLETS version": version,
            "Server status": statusServer,
            "TCP socket status": statusTcp,
            "WebSocket status": statusWebsocket, "Gateway": runningGateway, "LAN IP": lanip,
            "Webserver port": webserverPort, "WebSocket port": websocketPort,
            "Leshan IP": leshanip, "Leshan port": leshanPort,
            "TCP port": tcpPort, "BLE auto reconnect": autoReconnect, "HID": hid,
            "Alias": deviceAlias, "Leshan endpoint state": endpointActive, "Web app access": webappAccess,
            "Send status request": sendStatusRequest}


# Initialize and start the Eel app or web app. OSError because websocket is not closed correctly by Eel (Might be
# solved by future Eel update).
def startApp(path=None, socketlist=None):
    global guiType
    restartApp = False
    eel.init(f"gui")
    setStatus("Ready", "webserver")
    # GUI inactive
    try:
        if config.get("SBLETS", "GUI on") == "False":
            logging.info(f"SBLETS GUI is inactive!")
            guiType = "off"
        # Start as application
        elif guiType == "app" and restartApp or config.get("SBLETS", "Start as application") == "True" and path is None:
            guiType = "app"
            if config.get("SBLETS", "Allow web app access others") == "True":
                eel.start('index.html', size=(1920, 1080), mode="chrome", host=config.get("SBLETS", "LANIP"),
                          port=config.get("SBLETS", "Webserver port"), close_callback=startApp)
            else:
                eel.start('index.html', size=(1920, 1080), mode="chrome", host="localhost",
                          port=config.get("SBLETS", "Webserver port"), close_callback=startApp)
        # Web app with public access
        elif config.get("SBLETS", "Allow web app access others") == "True":
            guiType = "public"
            logging.info(f"Starting SBLETS GUI session as only a web app with public access!")
            eel.start('index.html', size=(1920, 1080), mode=None, host=config.get("SBLETS", "LANIP"),
                      port=config.get("SBLETS", "Webserver port"), close_callback=startApp)
        # Web app with private access only
        elif config.get("SBLETS", "Allow web app access others") == "False":
            guiType = "private"
            logging.info(f"Starting SBLETS GUI as only a web app with private access!")
            eel.start('index.html', size=(1920, 1080), mode=None, host="localhost",
                      port=config.get("SBLETS", "Webserver port"), close_callback=startApp)
    except OSError:
        # Eel does not close websocket on new app creation, so it throws and error but the same websocket can be used
        # across application so no problem.
        pass


if __name__ == "__main__":
    startApp()
