# Description: Test Server Application
# Author: Syncore Technologies AB
#
# Version: 1.0:
#
# Version: 1.1: Added support for newer BLE modules (Hqv BLE Service Frame) as described in ble_interface.
# Alexander Ström 2024-06-25
# Added features:
# * WebSocket as an alternative to TCP, but the WebSocket only supports
#   connecting to a BLE device. (Thread 3)
# * Webserver that hosts HAPP OMA DDF generator available on port 8085,
#   described in webserver.py (Thread 2)
#
# Version 1.2:
# Alexander Ström 2024-07-04
# Changes:
# * WebSocket now forwards the full message to the TCP socket, in other words, WebSocket supports all TCP commands.
# * The webserver now hosts multiple web components described in webserver.py.
# * Other minor changes like timeout, socket shutdown and session and config data.
# Added features:
# * Introduced new command 0x10 (16). This command makes a HAPP device scan,
#   earlier only accessible from the graphical web interface.
#
# Version 1.3: Alexander Ström 2024-07-16
# Changes:
# * Adjustments to the Bluetooth device handler (connecting and disconnected operations)
# * The gateway is now a thread instead of a multiprocessing process, this makes it runnable on a
#   non-UNIX machine. A thread event is used to terminate and control the thread instead of SIGTERM.
# Added features:
# * If configured SBLETS will try to reconnect to the BLE device when
#   connection is lost (Configured in config.ini or set in connect to GW request cmd)
# * SBLETS can now be compiled as an executable
# * GUI now displays HID of the connected BLE device
# * Other small GUI adjustments like status indicators
#
# Version 1.4: Alexander Ström 2024-08-02
# Changes:
# * Gateway can now be terminated even if callstop on win32 system
# * Optional event notification for code to work even when using bad winrt
# * HID and UUID is now fetched from the backend instead of frontend
# * Minor renaming and cleanup
# Added features:
# * Now more config parameters to change Leshan server port etc
# * Unique session UUID, on startup a small uuid with 8 characters
#   is generated and when connected to a BLE device SBLETS inherits its UUID
# * It is now possible to add an alias to an associated IPRID
# * It is now possible to add device secrets to be pushed to Leshan
# * Some new TCP commands to retrieve and set alias and key
#
# Version 1.5: Alexander Ström 2024-08-12
# Changes:
# * Larger changes to gui
# * GUI can be started both as a web app and a regular application
# * Navigation bar is now responsive
# * A log folder is now created if non existing
# * Fixed minor bugs with parse and more exception handlers
# * Started using version number x.x.* because software is starting to be distributed
# * Renaming of some tools [1.15.2]
# * WebScoket now returns TCP data to client [1.15.3]
# * Session data is now a global class instead of a file [1.15.3]
# Added features:
# * SBLETS discover protocol to find other SBLETS servers on the same network
# * SBLETS sends a status request every 5 minutes if activated in config file [1.15.2]
# * SBLETS now reports to operator if the computers Bluetooth service is deactivated [1.15.2]
# * Two new TCP server sender services (Leshan status) [1.15.2]
# * Two new commands, one for retrieving UUID and another for retrieving status code [1.15.3]
# * GUI now displays endpoint with href to Leshan on text and on nav Leshan button for ease of use [1.15.4]
# -----------------------------------------------------------------
import asyncio
import base64
import json
import logging
import argparse
import queue
import socket
import sys
import threading
import time
import traceback
import urllib.request
import uuid as uuidTool
import os
import requests
import eel
import configparser
import multiprocessing
import datetime
from logging.handlers import TimedRotatingFileHandler
from tools.addDeviceData import addAlias
from tools.findHappDevices import startSearch
import SynBlue  # Developed by Syncore and hold legacy components
import SynProtocol  # Knows how to encode and decode TCP data
from Gateway.gateway import launch
from webserver import *
from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket

global currentThread_Time
global currentThread_Gateway
global connect_datas
global gateway_stop

# Commands
ACK = 0xFE
NACK = 0xFF
ERROR = 0xEE

# Change SBLETS version in webserver.py

# Create a ConfigParser object
config = configparser.ConfigParser()

# Read the configuration file
config.read('config.ini')


# Example: variable = config.get('List', 'variable')

def bytearray_to_base64_str(bytearray_data):
    return base64.b64encode(bytearray_data).decode('utf-8')


def base64_str_to_bytearray(base64_str):
    return bytearray(base64.b64decode(base64_str))


# Callback for the Gateway
def callbackfunk_gateway(data, mac):
    send_connect_status(data, mac, 0x0E)


def callbackfunk_connect(data, mac):
    send_connect_status(data, mac, 0x07)


def mac_to_int(mac):
    return int(mac.replace(":", ""), 16)


def int_to_mac(in_data):
    s_mac = hex(in_data)[2:].upper().zfill(12)
    return ":".join([s_mac[i: i + 2] for i in range(0, 12, 2)])


def thread_connect_and_wait_for_disconnect(mac, timeout):
    # Handles the call to Connect and wait for disconnect
    logging.debug("Thread connect for device %s: starting", mac)
    SynBlue.Connect_And_Wait_For_Disconnect_Test(mac, callbackfunk_connect, timeout)
    # For test
    logging.debug("Thread connect for device %s: finishing", mac)


# WebSocket server as an alternative to the raw TCP socket. But the connection is always closed after 60 seconds to
# make it possible for multiple GUIs or interfaces to interact with SBLETS.
class SimpleEcho(WebSocket):
    # Forward message to TCP socket
    def __init__(self, server, sock, address):
        super().__init__(server, sock, address)

    def handleMessage(self):
        global tcpClient
        logging.info(f"(WebSocket) Received message from WebSocket: {self.data}")
        eel.putRLog(f"app.py (WebSocket): Received message from WebSocket: {self.data}")

        try:
            tcpClient = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcpClient.connect(('127.0.0.1', config.getint('TCP', 'Port')))
            tcpClient.send(self.data)
            tcpClient.settimeout(190.0)

            logging.debug(f"(WebSocket) Package sent to TCP server: {self.data}")
            eel.putRLog(f"app.py (websocket): Package sent to TCP server: {self.data}")

            response = tcpClient.recv(1024)
            logging.debug(f"(websocket) {response} Received from TCP Server, forwarding to websocket client")
            eel.putRLog(f"app.py (websocket): {response} Received from TCP Server, forwarding to websocket client")
            # Send the message back to a client
            self.sendMessage(str(response))

        except Exception as e:
            logging.error(f"(websocket) Error communicating with TCP server: {e}")
            eel.putRLog(f"app.py (websocket): Error communicating with TCP server: {e}")
            eel.changeConnectStatus(f"(websocket) Error communicating with TCP server: {e}")

        finally:
            # No response from shutdown command
            tcpClient.shutdown(socket.SHUT_WR)

            logging.debug(f"(websocket) Sending shutdown to TCP socket")
            eel.putRLog(f"app.py (websocket): Sending shutdown to TCP socket")

            tcpClient.close()
            logging.error(f"(websocket) Websocket to TCP tunnel closed")
            eel.putRLog(f"app.py (websocket): Websocket to TCP tunnel closed")
            self.close()

    def handleConnected(self):
        logging.info(f"{self.address} connected")
        # self.sendMessage(self.data)
        setStatus("Busy", "websocket")

    def handleClose(self):
        logging.info(f"{self.address} closed")
        setStatus("Ready", "websocket")


# This starts a synchronous websocket server that should be controlled by a thread
def start_websocket_server():
    try:
        server = SimpleWebSocketServer(config.get('SBLETS', 'LANIP'), config.get('WEBSOCKET', 'Port'), SimpleEcho)
        logging.info(f"WebSocket server started on port {config.get('WEBSOCKET', 'Port')}")
        eel.putRLog(
            f"app.py: WebSocket server started on port {config.get('WEBSOCKET', 'Port')}")  # Real time log on graphical web interface
        setStatus("Ready", "websocket")
        server.serveforever()
    except OSError:
        raise Exception("Not a valid or accepted IP or Port in config.ini!")


def server_part(q):
    global connect_data

    HOST = '127.0.0.1'  # The server hostname or IP address (Bind to all)
    PORT = config.getint('TCP', 'Port')  # The port used by the server (Pick a port number from 49152 through 65535)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # s.settimeout(10.0)
        # Ensure that you can restart your server quickly when it terminates
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Socket Keepalive on
        s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        # s.setsockopt(socket.SOL_TCP, socket.TCP_KEEPALIVE, 1)
        s.setsockopt(socket.SOL_TCP, socket.TCP_KEEPINTVL, 11)
        s.setsockopt(socket.SOL_TCP, socket.TCP_KEEPCNT, 3)
        # Set user timeout for unacknowledged data
        # s.setsockopt(socket.IPPROTO_TCP, socket.TCP_USER_TIMEOUT, 20000)  # 20-second timeout

        try:
            s.bind((HOST, PORT))

            logging.info(f"TCP socket started and binded to {HOST} and port {PORT}")
            eel.putRLog(f"app.py (TCP): TCP socket started and binded to {HOST} and port {PORT}")
            setStatus("Ready", "tcp")
            s.listen(1)  # One Client
            # logging.debug("Socket is listening")

        except socket.error:
            logging.warning("Socket connect failed! Loop up and try socket again")
            traceback.print_exc()
            time.sleep(5.0)
            pass

        # loop waiting for connections
        try:
            while True:
                try:
                    conn, addr = s.accept()

                    connect_data["conn"] = conn
                    connect_data["addr"] = addr

                    logging.debug("Connected by %s", addr)
                    setStatus("Ready", "tcp")

                    # conn.sendall(b"Hi from Server!") # Used During development only

                    # loop serving the new client
                    while True:
                        setStatus("Busy", "tcp")
                        try:
                            logging.debug("Wait For New Data:")
                            data = conn.recv(1024)

                            logging.debug("New Data Received:")
                            eel.putRLog("app.py (TCP): New Data Recived:")
                            q.put(data)
                            logging.debug(data)
                            setStatus("Ready", "tcp")
                            # eel.putRLog(data)

                            if not data:
                                logging.debug("Connection reset by peer")
                                eel.putRLog("app.py (TCP): Connection reset by peer")
                                break

                        except socket.timeout:
                            logging.debug("Socket timeout, loop and try recv() again")
                            time.sleep(5.0)
                            # traceback.print_exc()
                            pass

                        # except:
                        # traceback.print_exc()
                        # print 'Other Socket err, exit and try creating socket again'
                        # break from loop
                        # break

                        except:
                            logging.debug("Disconnected from %s", addr)
                            conn.close()
                            break

                except socket.timeout:
                    logging.debug("Socket timeout, loop and try accept() again")
                    # time.sleep( 5.0)
                    # traceback.print_exc()
                    pass

        finally:
            logging.debug("Socket Closed")
            setStatus("Dead", "tcp")
            s.close()

    logging.debug("With Socket Closed")


# SBLETS protocol is a way of discovering another SBLETS servers on the same network. SBLETS broadcast itself every
# 10 seconds and every 0.1 second search for these messages published by other SBLETS servers. Message must include
# the message type.
def sblets_discover_protocol():
    port = 5385
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setblocking(False)
    sock.bind(("", port))

    foundServers = []

    nextPublish = time.time() + 10  # Publish every 10th second

    logging.info(f"SBLETS protocol listening to {port}")
    eel.putRLog(
        f"app.py: SBLETS protocol listening to {port}")

    while True:
        time.sleep(0.1)
        try:
            data, addr = sock.recvfrom(1024)
            jsonString = data.decode('utf-8')

            # Check if broadcast message with SBLETSDISCPKG (Discover package)
            try:
                jsonObject = json.loads(jsonString)
                if jsonObject['messageType'] == "SBLETSDISCPKG" and jsonObject[
                    'ip'] != config.get("SBLETS", "LANIP" or "localhost"):
                    foundServer = {"customName": jsonObject['customName'], "guiAccess": jsonObject['guiAccess'], "endpoint": jsonObject['endpoint'], "ip": jsonObject['ip'],
                                   "port": jsonObject['port'],
                                   "version": jsonObject['version'], "timestamp": time.time()}
                    eel.addNewSBLETS(jsonObject['customName'], jsonObject['guiAccess'], jsonObject['endpoint'], jsonObject['ip'], jsonObject['port'],
                                     jsonObject['version'], time.time())  # Added to frontend
                    # When the array is empty
                    if not foundServers:
                        foundServers.append(foundServer)
                        sessionData.foundSbletsServers = foundServers
                        logging.info(f"Found new SBLETS server on: {jsonObject['ip']}")
                    # Skip comparing timestamp
                    foundServerNoTimestamp = {k: v for k, v in foundServer.items() if k != "timestamp"}
                    exist = False
                    for server in foundServers:
                        # Skip comparing timestamp
                        serverNoTimestamp = {k: v for k, v in server.items() if k != "timestamp"}
                        if str(serverNoTimestamp) == str(foundServerNoTimestamp):
                            exist = True
                    if not exist:
                            foundServers.append(foundServer)
                            sessionData.foundSbletsServers = foundServers
                            logging.info(f"Found new SBLETS server on: {jsonObject['ip']}")
            except json.JSONDecodeError:
                logging.debug(f"Received non-JSON data from {addr}: {jsonString}")
            except KeyError:
                logging.debug(f"SBLETSDISCPKG not correct from {addr}: {jsonString}")
        except BlockingIOError:
            # No data yet
            pass

        # Send a broadcast message
        if time.time() >= nextPublish:
            #logging.debug(f"Sending SBLETS discovery message")
            message = {
                "message": f"Hello other SBLETS servers, include me in your network!",
                "messageType": "SBLETSDISCPKG",
                "messageTypeVersion": "1",
                "guiAccess": config.get("SBLETS", "Allow web app access others"),
                "customName": config.get("SBLETS", "Name"),
                "endpoint": sessionData.uniqueSessionUUID,
                "ip": config.get("SBLETS", "LANIP"),
                "port": config.get("SBLETS", "Webserver port"),
                "version": getSbletsVersion(),
            }
            jsonData = json.dumps(message)
            sock.sendto(jsonData.encode('utf-8'), ("255.255.255.255", port))
            nextPublish = time.time() + 10  # Publish every 10th second


# Commands
def cmd_unpack_ip_and_port(data):
    try:

        if len(data) > 9:
            logging.debug("Size Data: %s", len(data))
            msg_ip = str(data[9:25], "utf-8")  # 16 Bytes
            msg_ip = msg_ip.strip().strip("\x00")
            logging.debug(f"IP: {msg_ip}")
            msg_port = int.from_bytes(data[25:27], "big")  # 2 Bytes
            logging.debug("Port: %s", msg_port)

            return msg_ip, msg_port
        else:
            return None, None

    except:
        return None, None


def cmd_unpack_mac_and_time(data):
    try:
        logging.debug("Size Data: %s", len(data))
        msg_mac = int.from_bytes(data[1:7], "big")  # 6 Bytes
        logging.debug("MAC: %s", hex(msg_mac))
        eel.putRLog(f"app.py: MAC: {hex(msg_mac)}")
        msg_time = int.from_bytes(data[7:8], "big")  # 1 Byte
        logging.debug("Time: %s", msg_time)

        if msg_time >= 1:
            return msg_mac, msg_time
        else:
            return None, None

    except:
        return None, None


# Mac without time
def cmd_unpack_mac(data):
    try:
        logging.debug("Size Data: %s", len(data))
        msg_mac = int.from_bytes(data[1:7], "big")  # 6 Bytes
        logging.debug("MAC: %s", hex(msg_mac))
        eel.putRLog(f"app.py: MAC: {hex(msg_mac)}")

        return msg_mac

    except:
        return None


def cmd_unpack_time(data):
    try:

        logging.debug("Size Data: %s", len(data))
        msg_data = int.from_bytes(data[1:], "big")
        logging.debug("Data: %s", hex(msg_data))

        if (len(data[1:])) == 1:
            return msg_data
        else:
            return None

    except:
        return None


def cmd_unpack_mac(data):
    logging.debug("Size Data: %s", len(data))
    msg_data = int.from_bytes(data[1:], "big")
    logging.debug("Data: %s", hex(msg_data))

    if (len(data[1:])) == 6:
        return msg_data
    else:
        return None


# Check whether to activate auto reconnect or not
def cmd_unpack_autoreconnect_value(data):
    try:

        if len(data) > 8:
            ReconnectValue = int.from_bytes(data[8], "big")
            logging.debug(f"Reconnect: {ReconnectValue}")
            if ReconnectValue == 1:
                config.set("BLE", "Auto reconnect", "True")
                return True
            else:
                config.set("BLE", "Auto reconnect", "False")
                return False
        else:  # If not defined in message read config file
            return eval(config.get('BLE', 'Auto reconnect'))

    except:
        return None


def cmd_unpack_alias(data):
    return str(data[1::], "utf-8")


def cmd_unpack_iprid(data):
    return str(data[1:33], "utf-8")


def cmd_unpack_secretkey(data):
    return str(data[33::], "utf-8")


def send_connect_status(data, mac, cmd):
    # Handle callbacks from Connect
    global connect_data
    connect_data["conn"]
    # print(data)
    # print(mac)
    if "Disconnected" in data:
        msg = bytearray()
        msg.append(0x09)
        mac_to_int(mac)
        msg.extend(mac_to_int(mac).to_bytes(6, "big"))
        connect_data["conn"].sendall(SynProtocol.encode_data(msg))
        logging.debug(f"Send Call Lost")
    elif "Connected:" in data:
        if "NO" in data:
            logging.debug("Send nack")
            # eel.putRLog(f"Send nack")
            connect_data["conn"].sendall(send_nack(cmd))
        elif "YES" in data:
            connect_data["conn"].sendall(send_ack(cmd))
            # Check if registered in Leshan
            checkIfRegistered = threading.Thread(target=check_if_registered)
            checkIfRegistered.start()


def send_result_data(cmd, data):
    return_val = bytearray()
    return_val.append(ACK)
    return_val.append(cmd)

    if isinstance(data, bytearray):
        return_val.extend(data)
    else:
        return_val.append(data)

    return SynProtocol.encode_data(return_val)


# Push stored secrets to Leshan server
def push_secrets_to_leshan(uuid):
    LeshanIP = config.get('LESHAN', 'IP')
    LeshanPort = config.get('LESHAN', 'Port')
    url = f"http://{LeshanIP}:{LeshanPort}/api/security/clients/"
    identity = uuid
    endpoint = str(uuidTool.UUID(uuid))
    key = getDeviceKey(uuid)
    if key == "unknown":
        logging.warning(f"No key pushed to Leshan!")
        eel.putRLog(f"app.py: No key pushed to Leshan!")
        return False

    data = {"endpoint": endpoint, "tls": {"mode": "psk", "details": {"identity": identity, "key": key}}}
    jsonData = json.dumps(data)
    headers = {"Content-Type": "application/json, text/plain, */*"}

    response = requests.put(url, data=jsonData, headers=headers)
    textResponse = response.text
    logging.debug(textResponse)
    logging.info(f"Success while pushing secrets to Leshan: {textResponse}")
    eel.putRLog(f"app.py: Success while pushing secrets to Leshan: {textResponse}")
    return True


# Read battery's HID from Leshan
# Started after check_if_registered() has reported that the device is online
@eel.expose
def get_device_hid(mac=None, uuid=None):
    if mac is None:
        mac = sessionData.connectedDeviceMac

    if uuid is None:
        HAPPDevices = sessionData.lastHAPPScan
        logging.debug(f"HAPPDevices={HAPPDevices}")
        # eel.putRLog(f"app.py: HAPPDevices={HAPPDevices}")

        for device in HAPPDevices:
            current_mac = device["mac"]

            # Format UUID with - as endpoint
            if current_mac == mac:
                str(uuidTool.UUID(hex=device["uuid"]))
                # eel.putRLog(f"app.py: {mac} might have endpoint: {uuid}")
                logging.debug(f"{mac} might have endpoint: {uuid}")
                sessionData.uniqueSessionUUID = uuid
                eel.pingFrontend()
                break
        else:
            sessionData.connectedDeviceHID = "No devices in list"
            eel.putRLog(f"app.py: No matching mac in list")
            logging.debug(f"No matching mac in list")
            return None

    LeshanIP = config.get('LESHAN', 'IP')
    LeshanPort = config.get('LESHAN', 'Port')

    try:
        contents = urllib.request.urlopen(f"http://{LeshanIP}:{LeshanPort}/api/clients/{uuid}/27003/0/19").read()
        data = json.loads(contents)
        # eel.putRLog(f"app.py: Received data from HTTP (HID): {data}")
        logging.debug(f"app.py: Received data from HTTP (HID): {data}")

        if 'content' in data and 'value' in data['content']:
            value = data['content']['value']
            inner_data = json.loads(value)

            hid = inner_data['Nodes'][0]['HID']
            logging.debug(f"{mac} has HID: {hid}")
            # eel.putRLog(f"app.py: {mac} has HID: {hid}")
            sessionData.connectedDeviceHID = hid
            sessionData.connectedDeviceHID = hid
            eel.changeConnectStatus(mac, True)
            eel.pingFrontend()

            return hid
        else:
            eel.putRLog(f"app.py: 'content' or 'value' not found in response.")
            logging.debug(f"'content' or 'value' not found in response.")
            return None

    except Exception as e:
        eel.putRLog(f"app.py: Failed to get HID for {mac} with uuid {uuid}. Error: {e}")
        logging.warning(f"Failed to get HID for {mac} with uuid {uuid}. Error: {e}")
        return None


# Checks if the BLE device is registered to Leshan
def check_if_registered():
    global connect_data
    connect_data["conn"]

    success = False
    maxRetries = 10
    waitTime = 3
    firstAttemptSeries = True
    sessionData.deviceConnectedToLeshan = "Retrieving"

    time.sleep(5)

    for attempt in range(maxRetries):
        success = False
        try:
            uuid = ""

            mac = sessionData.connectedDeviceMac
            if mac is None:
                # eel.putRLog(f"app.py: no MAC found")
                # logging.info(f"app.py: no MAC found")
                continue
            HAPPDevices = sessionData.lastHAPPScan
            logging.debug(f"HAPPDevices={HAPPDevices}")
            # eel.putRLog(f"app.py: HAPPDevices={HAPPDevices}")

            for device in HAPPDevices:
                current_mac = device["mac"]

                if current_mac == mac:
                    uuid = str(uuidTool.UUID(hex=device["uuid"]))
                    continue

            LeshanIP = config.get('LESHAN', 'IP')
            LeshanPort = config.get('LESHAN', 'Port')

            try:
                contents = urllib.request.urlopen(f"http://{LeshanIP}:{LeshanPort}/api/clients").read()
                data = json.loads(contents)
                for device in data:
                    endpoint = device.get("endpoint", None)
                    if endpoint == uuid:
                        eel.putRLog(f"app.py: {mac} with endpoint {endpoint} is online and connected to Leshan!")
                        logging.info(f"{mac} with endpoint {endpoint} is online and connected to Leshan!")
                        sessionData.deviceConnectedToLeshan = "True"
                        success = True
                        if firstAttemptSeries:
                            # Get HID when device is online
                            get_device_hid()
                            firstAttemptSeries = False
                            # Send device connected to Leshan to TCP
                            try:
                                msg = bytearray()
                                msg.append(0x15)
                                mac_to_int(mac)
                                msg.extend(mac_to_int(mac).to_bytes(6, "big"))
                                connect_data["conn"].sendall(send_ack(msg))
                            except ConnectionAbortedError:
                                logging.info("TCP Socket closed cant send server notify")
                                # If this takes a long time, TCP connection could have been closed
                                pass
                        # If send status request, wait 5 minutes and increase attempts to always check if online
                        else:
                            time.sleep(300)
                        if config.get("SBLETS", "Send regularly status request") == "True":
                            # This makes it a non-infinite loop incase device is disconnected
                            eel.putRLog(f"app.py: Sending status request to Leshan!")
                            logging.info(f"Sending status request to Leshan!")
                            maxRetries = maxRetries + 1
                            continue
                        else:

                            return

            except Exception as e:
                eel.putRLog(f"app.py: {mac} with endpoint {uuid} not online yet")
                logging.warning(f"{mac} with endpoint {uuid} not online yet")

        except Exception as e:
            logging.debug(f"Attempt {attempt + 1} to check device registration status error: {e}")
            eel.putRLog(f"app.py: Attempt {attempt + 1} to check device registration status error: {e}")
            sessionData.deviceConnectedToLeshan = "False"

        finally:
            if attempt < maxRetries - 1 and success is False and sessionData.connectStatusCode != 4:
                logging.debug(f"Attempt {attempt + 1} to check device registration status failed")
                eel.putRLog(f"app.py: Attempt {attempt + 1} to check device registration status failed")
                sessionData.deviceConnectedToLeshan = "False"
                time.sleep(waitTime)
            elif success is False:
                logging.warning(f"{mac} with endpoint {uuid} offline to long!")
                eel.putRLog(f"app.py: {mac} with endpoint {uuid} offline to long!")
                if sessionData.connectStatusCode != 4:
                    eel.changeConnectStatus("Device failed to register in Leshan!")

    logging.warning(f"Exiting thread to check if device is registered without progress")
    eel.putRLog(f"Exiting thread to check if device is registered without progress")
    if success:
        sessionData.deviceConnectedToLeshan = "True"
    else:
        sessionData.deviceConnectedToLeshan = "False"
        # Send device disconnected to Leshan to TCP
        try:
            msg = bytearray()
            msg.append(0x16)
            connect_data["conn"].sendall(SynProtocol.encode_data(msg))
        except ConnectionAbortedError:
            logging.info("TCP Socket closed cant send server notify")
            # If this takes a long time, TCP connection could have been closed
            pass


# def send_result_data_2(cmd, data):
# # TODO Remove
# return_val = bytearray()
# return_val.append(ACK)
# return_val.append(cmd)
# return_val.append(data)

# return SynProtocol.encode_data(return_val)


def send_ack(cmd):
    return_val = bytearray()
    return_val.append(ACK)
    return_val.append(cmd)

    return SynProtocol.encode_data(return_val)


def send_nack(cmd):
    return_val = bytearray()
    return_val.append(NACK)
    return_val.append(cmd)

    return SynProtocol.encode_data(return_val)


def send_error(cmd, error_code):
    return_val = bytearray()
    return_val.append(ERROR)
    return_val.append(cmd)
    return_val.append(error_code)

    return SynProtocol.encode_data(return_val)


def parse_msg(data):
    print("Message detected!")
    logging.debug("Message detected!")
    global currentThread_Time
    global connect_data
    global currentThread_Gateway
    global gateway_stop
    global HAPPDevices
    connection = connect_data["conn"]

    # Received Command
    msg_cmd = data[0]
    logging.debug("cmd: %s", msg_cmd)
    eel.putRLog(f"app.py: cmd: {msg_cmd}")

    # -- Print warning for deprecated or unsupported commands --
    if msg_cmd == 0x06 or msg_cmd == 0x0B or msg_cmd == 0x0C:
        logging.warning(f"cmd: {msg_cmd} is a legacy and deprecated command consider using 0x10 (16) instead!")
        eel.putRLog(f"app.py: cmd: {msg_cmd} is a legacy and deprecated command consider using 0x10 (16) instead!")

    if msg_cmd == 0x08 and sys.platform == 'win32':
        logging.warning(f"cmd: {msg_cmd} is not supported on Windows!")
        eel.putRLog(f"app.py: cmd: {msg_cmd} is not supported on Windows!")
    # ----------------------------------------------------------

    # Connect to SBLETS server
    if msg_cmd == 0x04:
        connect_data["user"] = True
        logging.debug("User connected: %s", connect_data["user"])

        # Init Bluetooth
        # subprocess.run() # If needed

        # Return SBLETS UUID when connecting.
        # OBS!
        # At the start, SBLETS has a short UUID (8 bytes), but when connected
        # to a BLE device it gets the devices UUID
        return_data = bytearray()
        uuid_ascii = bytes(sessionData.uniqueSessionUUID, "ascii")
        return_data.extend(uuid_ascii)

        connection.sendall(send_result_data(msg_cmd, return_data))
        # connection.sendall(send_ack(msg_cmd))
    # Disconnect from SBLETS server
    elif msg_cmd == 0x05:
        if connect_data["user"] == True:
            connect_data["user"] = False
            connection.sendall(send_ack(msg_cmd))
        else:
            connect_data["user"] = False
            connection.sendall(send_nack(msg_cmd))
        logging.debug("User connected: %s", connect_data["user"])

    # Alexander Ström 2024-07-18 This is a legacy command and replaced by HAPP Device Finder cmd 16
    # List Devices
    elif msg_cmd == 0x06:
        logging.debug("Execute Cmd 0x06")

        timeout = cmd_unpack_time(data)

        if timeout:

            Devices = SynBlue.List_Of_Devices_Test(timeout)
            logging.debug("The Devices Found is: ")
            if Devices:

                return_data = bytearray()

                return_data.extend(
                    len(Devices).to_bytes(4, byteorder="big", signed=False)
                )  # Nr of device 4 Byte

                for dev in Devices:
                    logging.debug(dev)
                    # Device Mac adress 6 byte
                    mac = dev["mac_address"].replace(":", "")
                    return_data.extend(bytearray.fromhex(mac))

                    # Device Name null terminted ASCII String
                    name_ascii = bytes(dev["name"], "ascii") + b"\x00"
                    return_data.extend(name_ascii)

                # Send Data
                connection.sendall(send_result_data(msg_cmd, return_data))

                # if False:
                # # Decode Test Funktion som ska ligga i labview
                # print(return_data)

                # data = return_data[4:]
                # no_of_device = int.from_bytes(return_data[0:4], "big")
                # print(no_of_device)
                # print(data)
                # print(len(data))

                # index = 0
                # unpacked_device = 0
                # while unpacked_device < no_of_device:
                # # while len(data) - index > 6:
                # print(index, " XXX ", len(data))
                # mac_a = data[index : index + 6]

                # mac_a = int.from_bytes(mac_a, "big")
                # s_mac = hex(mac_a)[2:].upper().zfill(12)
                # m = ":".join([s_mac[i : i + 2] for i in range(0, 12, 2)])

                # print(m)
                # y = data[index + 6 :].split(b"\x00")

                # # print(len(y[0]))
                # name = y[0].decode("ascii")
                # index = index + (len(y[0]) + 7)
                # print(name)
                # # print(index)
                # unpacked_device += 1

            # No devices found
            else:
                logging.debug("No devices found")
                connection.sendall(send_nack(msg_cmd))
        # Missing paramter
        else:
            connection.sendall(send_error(msg_cmd, 1))

    # Connect Device
    elif msg_cmd == 0x07:

        mac_address, timeout = cmd_unpack_mac_and_time(data)

        if mac_address and timeout:
            logging.debug("Execute Cmd 0x07 %s", int_to_mac(mac_address))

            # For Test 
            # result = SynBlue.Connect_Test(int_to_mac(mac_address)) # Was comment away
            # logging.debug("Test 6 - Connect device result = %s", result) # Was comment away

            connect_thread = threading.Thread(
                target=thread_connect_and_wait_for_disconnect,
                args=(
                    int_to_mac(mac_address),
                    timeout,
                ),
            )
            connect_thread.start()

        else:
            # Missing paramter
            connection.sendall(send_error(msg_cmd, 1))

    # Alexander Ström 2024-07-18 Not supported on Windows
    # Disconnect Device
    elif msg_cmd == 0x08:

        mac_addr = cmd_unpack_mac(data)
        if mac_addr:
            logging.debug("Execute Cmd 0x08 %s", int_to_mac(mac_addr))
            result = SynBlue.Disconnect_Test(int_to_mac(mac_addr))
            logging.debug(result)

            if result == SynBlue.Return_type.SUCCESS:
                connection.sendall(send_ack(msg_cmd))
            else:
                connection.sendall(send_nack(msg_cmd))

        else:
            # Missing paramter
            connection.sendall(send_error(msg_cmd, 1))

    elif msg_cmd == 0x0A:  # FOTA

        logging.debug("Execute FOTA Cmd 0x0A")

        # msg_data_lenght = int.from_bytes(data[1:5], "big")
        # msg_data = data[5:]
        # logging.debug("Data lenght: %s", msg_data_lenght)
        # logging.debug("Data: %s", msg_data)
        # logging.debug((len(msg_data) == msg_data_lenght))

        # binary_file = open("test_2.png", "wb")
        # binary_file.write(msg_data)
        # binary_file.close()

    # Alexander Ström 2024-07-18 This is a legacy command and replaced by HAPP Device Finder cmd 16
    # Get Manufacturer data (Need to connect)
    elif msg_cmd == 0x0B:
        mac_addr, timeout = cmd_unpack_mac_and_time(data)

        if mac_addr and timeout:
            logging.debug("Execute Cmd 0x0B %s", int_to_mac(mac_addr))

            try:

                result = SynBlue.Get_Need_To_Connect_Test(int_to_mac(mac_addr), timeout)

                if result == -1:
                    logging.debug("No data found")
                    connection.sendall(send_nack(msg_cmd))

                else:
                    logging.debug("Get_Manufacturer_Data: ")
                    logging.debug(result)
                    connection.sendall(send_result_data(msg_cmd, result))

            except Exception as e:
                logging.error(f"Unexpected Error: {e}")
                connection.sendall(send_error(msg_cmd, 2))

        else:
            # Missing paramter
            connection.sendall(send_error(msg_cmd, 1))

    # Alexander Ström 2024-07-18 This is a legacy command and might stop working after bleak update
    # Get BLE device advertising data
    elif msg_cmd == 0x0C:
        mac_addr, timeout = cmd_unpack_mac_and_time(data)

        if mac_addr and timeout:
            logging.debug("Execute Cmd 0x0C %s", int_to_mac(mac_addr))

            try:

                result = SynBlue.Get_Advertisement_Data_Test(
                    int_to_mac(mac_addr), timeout
                )
                if result is None:
                    logging.debug("No data found")
                    connection.sendall(send_nack(msg_cmd))
                else:
                    logging.debug("Get_Advertising_Data Response Data: ")
                    logging.debug(result)
                    connection.sendall(send_result_data(msg_cmd, result))

            except Exception as e:
                logging.error(f"Unexpected Error: {e}")
                connection.sendall(send_error(msg_cmd, 2))
        else:
            # Missing paramter
            connection.sendall(send_error(msg_cmd, 1))

    # Advertisment Time Test
    elif msg_cmd == 0x0D:

        mac_addr, timeout = cmd_unpack_mac_and_time(data)

        if mac_addr and timeout:
            logging.debug("Execute Cmd 0x0D %s %s", int_to_mac(mac_addr), timeout)

            try:

                timestamps = SynBlue.Advertisement_Period_Test(timeout, int_to_mac(mac_addr))
                logging.debug("Advertisement timestamp [ms]")
                logging.debug(timestamps)

                if (len(timestamps)) > 0:

                    return_data = bytearray()

                    return_data.extend(
                        len(timestamps).to_bytes(2, byteorder="big", signed=False)
                    )  # Nr of timestamps 2 Bytes

                    if len(timestamps) > 0:
                        start_timestamp = timestamps[0]

                    for timestamp in timestamps:
                        timestamp_ms = int(
                            (timestamp - start_timestamp) / 1000000
                        )  # ns to ms
                        logging.debug(timestamp_ms)

                        return_data.extend(
                            timestamp_ms.to_bytes(4, byteorder="big", signed=False)
                        )  # 4 Bytes

                    # Send Data
                    connection.sendall(send_result_data(msg_cmd, return_data))
                # No Timestamps found
                else:
                    logging.debug("No timestamps found")
                    connection.sendall(send_nack(msg_cmd))

            except Exception as e:
                logging.error(f"Unexpected Error: {e}")
                connection.sendall(send_error(msg_cmd, 2))

        else:
            # Missing paramter
            connection.sendall(send_error(msg_cmd, 1))

    elif msg_cmd == 0x0E:  # Start Gateway
        # saveSessionData("macToGWdata", bytearray_to_base64_str(data))
        deviceUUID = ""

        logging.debug("Execute Start Gateway Cmd 0x0E")

        mac_addr, timeout = cmd_unpack_mac_and_time(data)
        mac = int_to_mac(mac_addr)
        autoreconnect = cmd_unpack_autoreconnect_value(data)  # Check if auto reconnect should be active or not
        ip, port = cmd_unpack_ip_and_port(data)

        for x in range(4):
            breakOuterLoop = False
            HAPPDevices = sessionData.lastHAPPScan
            if HAPPDevices is None:
                HAPPDevices = startSearch()
            for device in HAPPDevices:
                currentMac = device["mac"]
                deviceUUID = device["uuid"]  # Used later to get alias for the BLE device
                sessionData.connectedDeviceIPRID = deviceUUID

                if currentMac == mac:
                    logging.debug(f"{mac_addr} is in HAPP device list, starting gateway")
                    eel.putRLog(f"app.py: {mac_addr} is in HAPP device list, starting gateway")
                    # Add device secrets to Leshan
                    push_secrets_to_leshan(deviceUUID)
                    breakOuterLoop = True
                    break

            if breakOuterLoop:
                break
            else:
                HAPPDevices = startSearch()

            if x == 3:
                connection.sendall(send_error(msg_cmd, 3))
                return None

        if mac_addr and timeout:

            try:

                # The gateway is callstop, kill it! # TODO Fix the close
                try:
                    if not currentThread_Gateway is None:
                        logging.debug(currentThread_Gateway.is_alive())
                        if currentThread_Gateway.is_alive():
                            gateway_stop.set()  # Set triggers gateway.monitor_thread which terminates thread
                            currentThread_Gateway.join()
                            logging.debug("Gateway Terminated")
                            # time.sleep(20)
                except AttributeError as e:
                    logging.error(f"Error terminating currentThread_Gateway: {e}")

                except Exception as e:
                    logging.error(f"Unexpected Error: {e}")
                    connection.sendall(send_error(msg_cmd, 2))

                # If Leshan on another machine get IP
                if port is None:
                    port = 5684
                if ip is None:
                    ip = config.get('LESHAN', 'IP')

                gateway_stop = threading.Event()

                # Start a new process with the gateway
                currentThread_Gateway = threading.Thread(
                    target=launch,
                    args=(
                        mac,  # From Client
                        "random",  # FG, Hardcoded
                        "adapter",  # FG, Dummy data
                        "0",  # FG, Dummy data
                        "0",  # FG, Dummy data
                        port,  # From Client
                        ip,  # From Client
                        True,  # Debug On/Off
                        callbackfunk_gateway,  # Server Callback to Client
                        timeout,  # From Client
                        autoreconnect,  # Auto reconnect
                        gateway_stop,  # SIGTERM solution for threading compatible with Windows
                    ),
                )

                currentThread_Gateway.start()
                logging.debug(f"Gateway Started with auto reconnect: {autoreconnect}")
                eel.putRLog(f"app.py: Gateway Started with auto reconnect: {autoreconnect}")

                if currentThread_Gateway.is_alive():
                    sessionData.runningGateway = True

                getDeviceAlias(deviceUUID)  # Get alias for the connected BLE device

            except Exception as e:
                logging.error(f"Unexpected Error: {e}")
                connection.sendall(send_error(msg_cmd, 2))

        else:
            # Missing paramter
            connection.sendall(send_error(msg_cmd, 1))

    elif msg_cmd == 0x0F:  # Stop Gateway
        logging.debug("Execute Stop Gateway Cmd 0x0F")

        try:

            # If the gateway is not closed already
            if not currentThread_Gateway is None:
                if currentThread_Gateway.is_alive():
                    gateway_stop.set()
                    currentThread_Gateway.join()
                    logging.debug("Gateway Terminated")
                    eel.putRLog(f"app.py: Gateway Terminated")
                    eel.changeConnectStatus("Gateway Terminated")
                    sessionData.connectStatusCode = 0
                    sessionData.runningGateway = False
                    clearDeviceData()

                currentThread_Gateway = None
                logging.debug("Gateway Closed")
                eel.putRLog(f"app.py: Gateway Closed")

            connection.sendall(send_ack(msg_cmd))

        except Exception as e:
            logging.error(f"Unexpected Error: {e}")
            # Send Exception
            connection.sendall(send_error(msg_cmd, 2))

    elif msg_cmd == 0x10:  # List HAPP devices with associated info
        logging.debug("Execute Cmd 0x10")

        timeout = cmd_unpack_time(data)

        HAPPDevices = startSearch(timeout)
        logging.debug("The Devices Found is: ")
        if HAPPDevices:

            return_data = bytearray()

            return_data.extend(
                len(HAPPDevices).to_bytes(4, byteorder="big", signed=False)
            )  # Nr of device 4 Byte

            for dev in HAPPDevices:
                logging.debug(dev)
                # Device Mac adress 6 byte
                mac = dev["mac"].replace(":", "")
                # eel.putRLog(f"Mac {mac}")
                return_data.extend(bytearray.fromhex(mac))
                # eel.putRLog(f"Mac bytearray {bytearray.fromhex(mac)}")

                # Device uuid ASCII String
                name_ascii = bytes(dev["uuid"], "ascii")
                return_data.extend(name_ascii)

                # Device NTC (Need to Connect) ASCII String
                NTC = bytes(dev["NTC"])
                return_data.extend(NTC)

                # Device DNC (Do not Connect) ASCII String
                DNC = bytes(dev["DNC"])
                return_data.extend(DNC)

                # Device rssi ASCII String
                rssi_ascii = bytes(dev["rssi"], "ascii")
                return_data.extend(rssi_ascii)

                # Device alias null terminted ASCII String
                alias_ascii = bytes(dev["alias"], "ascii") + b"\x00"
                return_data.extend(alias_ascii)

            # Send Data
            connection.sendall(send_result_data(msg_cmd, return_data))

        # No devices found
        else:
            logging.debug("No devices found")
            connection.sendall(send_nack(msg_cmd))

    elif msg_cmd == 0x11:  # Return connected device HID
        logging.debug("Execute Cmd 0x11")

        if sessionData.connectedDeviceHID is not None:
            logging.debug(sessionData.connectedDeviceHID)
            return_data = bytearray()

            hid_ascii = bytes(sessionData.connectedDeviceHID, "ascii")
            return_data.extend(hid_ascii)

            # Send Data
            connection.sendall(send_result_data(msg_cmd, return_data))

        # No devices found
        else:
            logging.debug("No HID present")
            connection.sendall(send_nack(msg_cmd))

    elif msg_cmd == 0x12:  # Return connected device Alias
        logging.debug("Execute Cmd 0x12")

        if sessionData.connectedDeviceAlias is not None:

            return_data = bytearray()

            alias_ascii = bytes(sessionData.connectedDeviceAlias, "ascii")
            return_data.extend(alias_ascii)

            # Send Data
            connection.sendall(send_result_data(msg_cmd, return_data))

        # No devices found
        else:
            logging.debug("No alias registered")
            connection.sendall(send_nack(msg_cmd))

    elif msg_cmd == 0x13:  # Set new alias for the connected device
        logging.debug("Execute Cmd 0x13")

        if sessionData.connectStatusCode == 1 and sessionData.connectedDeviceIPRID is not None:
            newAlias = cmd_unpack_alias(data)
            if addAlias(sessionData.connectedDeviceIPRID, newAlias):
                connection.sendall(send_ack(msg_cmd))
                sessionData.connectedDeviceAlias = newAlias
                connection.sendall(send_ack(msg_cmd))
                eel.pingFrontend()
            else:
                logging.debug("Failed to register alias")
                connection.sendall(send_nack(msg_cmd))
        # No devices found
        else:
            logging.debug("Not allowed to set new alias")
            connection.sendall(send_nack(msg_cmd))

    elif msg_cmd == 0x14:  # Set new key for IPRID
        logging.debug("Execute Cmd 0x14")

        iprid = cmd_unpack_iprid(data)
        key = cmd_unpack_secretkey(data)

        if addKey(iprid, key):
            connection.sendall(send_ack(msg_cmd))
        else:
            connection.sendall(send_nack(msg_cmd))

    elif msg_cmd == 0x17:  # Return SBLETS UUID (8 characters is from SBLETS, and 16 characters is from connected HAPP)
        # device)
        logging.debug("Execute Cmd 0x17")

        if getSessionData("uniqueSessionUUID") is not None:
            return_data = bytearray()

            uuid = bytes(sessionData.uniqueSessionUUID, "ascii")
            return_data.extend(uuid)

            # Send Data
            connection.sendall(send_result_data(msg_cmd, return_data))

        # No devices found
        else:
            logging.debug("No UUID present!")
            connection.sendall(send_nack(msg_cmd))

    elif msg_cmd == 0x18:  # Return connect status code
        logging.debug("Execute Cmd 0x18")

        if sessionData.connectStatusCode is not None:

            # Send Data
            connection.sendall(send_result_data(msg_cmd, sessionData.connectStatusCode))

        # No devices found
        else:
            logging.debug("No status code present!")
            connection.sendall(send_nack(msg_cmd))

    else:
        logging.warning("Not a valid cmd: %s", msg_cmd)
        # Not Valid Cmd
        connection.sendall(send_error(msg_cmd, 3))

    return None


def process_cmd(data_in):
    logging.debug("Process Data:")
    setStatus("Busy", "server")
    logging.debug(data_in)
    logging.debug("Size Data: %s", len(data_in))

    decoded_data = SynProtocol.decode_data(bytearray(data_in))

    parse_msg(decoded_data)
    logging.debug("Process Data Done")
    setStatus("Ready", "server")


def main():
    global connect_data
    global currentThread_Gateway
    connect_data = {"user_connected": False, "conn": "", "addr": None}
    currentThread_Gateway = None

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="SBLETS Server Application",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Increase verbosity to log all data going through",
    )

    args = parser.parse_args()

    # Check that config file is correct
    try:
        # According to 1.15.2
        config.get("TCP", "Port")
        config.get("WEBSOCKET", "Port")
        config.get("SBLETS", "Name")
        config.get("SBLETS", "LANIP")
        config.get("SBLETS", "Webserver port")
        config.get("SBLETS", "Device lookup path")
        config.get("SBLETS", "Device secrets path")
        config.get("SBLETS", "GUI on")
        config.get("SBLETS", "Start as application")
        config.get("SBLETS", "Allow web app access others")
        config.get("SBLETS", "Send regularly status request")
        config.get("LESHAN", "IP")
        config.get("LESHAN", "Port")
        config.get("LESHAN", "Leshan objects path")
        config.get("BLE", "Auto reconnect")
    except Exception as e:
        logging.warning(f"{e} declared in config.ini, SBLETS might not work correclty!")

    logging.getLogger("bleak").level = logging.INFO
    # Set up logging to file
    # logfolder = os.path.dirname(__file__) + "/logs/"
    # logfolder = f"/var/log/{config.get('SBLETS', 'folderPath')}/"
    logfolder = f"log/"  # Display log in working directory
    logfile = logfolder + "Log_" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S.log")
    formatter = logging.Formatter('%(asctime)s.%(msecs)03d | %(levelname)s | %(filename)s: %(message)s', "%H:%M:%S")
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        # If on windows, the application is executable, so use another log path
        if not os.path.exists(os.getcwd() + "/" + logfolder):
            os.makedirs(os.getcwd() + "/" + logfolder)
        try:
            handler = TimedRotatingFileHandler(logfile, when="midnight", interval=1)
        except FileNotFoundError:
            raise Exception("No log folder could be created, please manually create a 'log' folder in the root of the "
                            "executable!")
    else:
        logfolder = config.get('SBLETS', 'Log folder path')
        logfile = logfolder + "/Log_" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S.log")
        handler = TimedRotatingFileHandler(logfile, when="midnight", interval=1)
    handler.suffix = "%Y-%m-%d"
    setStatus("Starting", "server")
    print(f"SBLETS{getSbletsVersion()} is online!")

    handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    logger.addHandler(handler)

    # Print to console
    if False:
        # define a Handler which writes INFO messages or higher to the sys.stderr
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        # set a format which is simpler for console use
        formatter = logging.Formatter("%(name)-12s: %(levelname)-8s %(message)s")
        # tell the handler to use this format
        console.setFormatter(formatter)
        # add the handler to the root logger
        logging.getLogger("").addHandler(console)

    # Incoming data seq
    command_queue = queue.Queue()

    # Start webserver
    setStatus("Starting", "webserver")
    webserverThread = threading.Thread(target=startApp)
    webserverThread.start()
    logging.info(f"Webserver Started on port 8085")
    if config.get("SBLETS", "Allow web app access others") == "True":
        logging.info(f"Visit Web GUI on: http://{config.get('SBLETS', 'LANIP')}:8085")
    else:
        logging.info(f"Visit Web GUI on: http://localhost:8085")

    time.sleep(1)  # Let webserver start before anything else

    x = threading.Thread(target=server_part, args=(command_queue,))
    x.start()
    # logging.info("TCP Server Started")

    # Start the WebSocket server in a separate thread
    websocketThread = threading.Thread(target=start_websocket_server)
    websocketThread.start()

    sbletsProtocol = threading.Thread(target=sblets_discover_protocol)
    sbletsProtocol.start()

    setStatus("Ready", "server")

    shortUUID = str(uuidTool.uuid4())[:8]

    sessionData.uniqueSessionUUID = shortUUID
    sessionData.startupUniqueSessionUUID = shortUUID
    eel.pingFrontend()

    cmd_data = []
    start_cmd_found = False
    end_cmd_found = False

    while True:

        try:

            if not command_queue.empty():

                item = command_queue.get()
                if item is None:
                    logging.debug("if item is None")
                    break
                logging.debug("New Item: ")
                logging.debug(item)

                for b in item:

                    if start_cmd_found:
                        end_cmd_found = False

                        if b == 0x03:
                            logging.debug("ETX Found")
                            process_cmd(cmd_data)
                            cmd_data.clear()
                            start_cmd_found = False

                        elif b == 0x02:
                            logging.warning("STX Found before ETX")
                            # Found Start before the end, clear buffer
                            cmd_data.clear()
                        else:
                            cmd_data.append(b)

                    else:
                        if b == 0x02:
                            logging.debug("STX Found")
                            start_cmd_found = True

                command_queue.task_done()

            else:
                time.sleep(0.5)
                if not x.is_alive():
                    logging.debug("TCP socket thread dead, restarting!")
                    eel.putRLog("app.py: TCP socket thread dead, restarting!")
                    x.start()

        except Exception as e:
            logging.error(f"Unexpected Error: {e}")


if __name__ == "__main__":
    main()
