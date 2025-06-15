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
import os
import ctypes
from json import JSONDecodeError
import eel
from SessionData import sessionData
from simulate_imc import runSimRev50, runSimRev150, runSimRev250, runSimHighAndLow, runSimLong
from plot import parse_log_time_per_speed, parse_histogram, plot_bar_red, plot_bar_blue, plot_bar, plot_scatter, plot_step, plot_heatmap
from threading import Thread
import requests
import datetime

# Version of SBLETS
version = "1.5.5"

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

@eel.expose
def startSimRev50():
    Thread(target=runSimRev50).start()
    
@eel.expose
def startSimRev150():
    Thread(target=runSimRev150).start()

@eel.expose
def startSimRev250():
    Thread(target=runSimRev250).start()

@eel.expose
def startSimHighAndLow():
    Thread(target=runSimHighAndLow).start()

@eel.expose
def startSimLong():
    Thread(target=runSimLong).start()

@eel.expose
def list_simlog_files(_=None):
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.getcwd()

    log_dir = os.path.join(base_path, 'simlog')
    if not os.path.exists(log_dir):
        return []

    return sorted(
        [f for f in os.listdir(log_dir) if f.startswith('logger_') and f.endswith('.log')],
        reverse=True
    )

@eel.expose
def list_leshan_instances(_=None):
    """
    List all instances under object 27004 in the Leshan server.
    """
    base_url = f"http://{config.get('LESHAN', 'IP')}:{config.get('LESHAN', 'Port')}/api"
    clients_resp = requests.get(f"{base_url}/clients")
    clients = clients_resp.json()
    client_id = clients[0]["endpoint"]

    client_info_url = f"{base_url}/clients/{client_id}"
    client_info_resp = requests.get(client_info_url)
    client_info = client_info_resp.json()
    object_links = client_info.get("objectLinks", [])

    instance_ids = []
    for link in object_links:
        url = link.get("url", "")
        if url.startswith("/27004/"):
            parts = url.strip("/").split("/")
            if len(parts) == 2:
                instance_ids.append(parts[1])

    return instance_ids

@eel.expose
def get_device_stats(_=None):
    """
    Fetch device status from the Leshan server for object IDs 3 and 27003.
    """
    base_url = f"http://{config.get('LESHAN', 'IP')}:{config.get('LESHAN', 'Port')}/api"
    
    try:
        clients_resp = requests.get(f"{base_url}/clients")
        clients_resp.raise_for_status()
        clients = clients_resp.json()
    except Exception as e:
        return {"error": f"Failed to fetch clients: {str(e)}"}

    if not clients:
        return {"error": "No clients found"}

    client_id = clients[0]["endpoint"]

    # Define resources to query
    object_id = "3"
    object_hva_id = "27003"
    ins_id = "0"

    resources = [
        (object_id, ins_id, "2", "serial_number"),
        (object_id, ins_id, "9", "battery_level"),
        (object_id, ins_id, "20", "battery_status"),
        (object_id, ins_id, "11", "error_code"),
        (object_hva_id, ins_id, "6", "total_motor_running_time"),
        (object_hva_id, ins_id, "8", "total_usage_running_time"),
    ]

    result = {}

    for obj_id, ins_id, res_id, label in resources:
        resource_url = f"{base_url}/clients/{client_id}/{obj_id}/{ins_id}/{res_id}"
        try:
            res_resp = requests.get(resource_url)
            res_resp.raise_for_status()
            res_data = res_resp.json()
            content = res_data.get("content", {})
            value = content.get("value", "N/A")
            result[label] = value
        except requests.RequestException as e:
            result[label] = f"Error: {str(e)}"
        except Exception as e:
            result[label] = f"Unexpected error: {str(e)}"

    return result

@eel.expose
def get_histogram_data(instance_id):
    """
    Fetch histogram data from the Leshan server for a specific instance ID.
    """
    base_url = f"http://{config.get('LESHAN', 'IP')}:{config.get('LESHAN', 'Port')}/api"
    
    try:
        # Step 1: Get clients
        clients_resp = requests.get(f"{base_url}/clients")
        clients_resp.raise_for_status()
        clients = clients_resp.json()

        if not clients:
            return {"error": "No clients found"}

        client_id = clients[0]["endpoint"]

        # Step 2: Build URL for histogram data
        object_id = "27004"
        histogram_id = "6"
        resource_url = f"{base_url}/clients/{client_id}/{object_id}/{instance_id}/{histogram_id}"

        # Step 3: Fetch histogram resource data
        response = requests.get(resource_url, headers={"Accept": "application/json"})
        response.raise_for_status()
        data = response.json()

        # Step 4: Extract value like in fetch_value_from_url
        content = data.get('content', {})
        if 'values' in content and '0' in content['values']:
            return content['values']['0']
        return content.get('value', None)

    except requests.RequestException as e:
        return {"error": str(e)}

@eel.expose
def generate_plot(logfile, instance_id, plot_type):
    """
    Generate a plot from logfile and return base64-encoded PNG for frontend.
    """
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.getcwd()

    filepath = os.path.join(base_path, 'simlog', logfile)
    if not os.path.exists(filepath):
        return None

    try:
        log_revspeeds, log_times = parse_log_time_per_speed(filepath)
    except Exception as e:
        print(f"Error parsing log: {e}")

    try:
        hex_data = get_histogram_data(instance_id)
        revspeeds, times = parse_histogram(hex_data)
    except Exception as e:
        print(f"Error getting conncativity device histogram: {e}")

    if plot_type == "barplot_red":
        return plot_bar_red(log_revspeeds, log_times)

    if plot_type == "barplot_blue":
        return plot_bar_blue(revspeeds, times)
    
    if plot_type == "barplot":
        return plot_bar(revspeeds, times, log_revspeeds, log_times)
    
    if plot_type == "stepplot":
        return plot_step(revspeeds, times, log_revspeeds, log_times)
    
    if plot_type == "scatterplot":
        return plot_scatter(revspeeds, times, log_revspeeds, log_times)
    
    if plot_type == "heatmap":
        return plot_heatmap(revspeeds, times, log_revspeeds, log_times)

    # Placeholder for other plots
    return None
    
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
