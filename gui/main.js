CONFIG = {}

// Makes it possible for python to add text to different log div in GUI compared to the main real time log box
eel.expose(addToLog);
function addToLog(text, element) {
    var modelGen = document.getElementById('log_modelGen');
    var HAPPfinder = document.getElementById('log_HAPPfinder');

    if (element == "modelGen"){
        modelGen.innerHTML += text + '<br>';
    }
    else if (element == "HAPPfinder"){
        HAPPfinder.innerHTML += text + '<br>';
    }
}

// Get session data from python webserver.py
async function fetchInfo() {
    var LANIP, portWS, tcpPort, leshanIP, leshanPort, hid, alias, leshanEndpointState, customName, keepAliveToLeshan, uuid;

    var dontDisplayInSessionData = ["HID", "Alias", "TCP port", "WebSocket port", "Leshan endpoint state", "Send status request"] // Values returned from readData not to be displayed directly in infoBox

    try {
        let configList = await eel.readData()();
        let infoBox = document.getElementById('infoDisplay');
        infoBox.innerHTML = "";
        for (const [key, value] of Object.entries(configList)) {
            if (!(dontDisplayInSessionData.includes(key))) {
                infoBox.innerHTML += `<strong id='${key}'>${key}:</strong> ${value}<br>`;
            }
            if (key == "Leshan IP") {leshanIP = value}
            if (key == "Leshan port") {leshanPort = value}
            if (key == "LAN IP"){LANIP = value}
            if (key == "WebSocket port"){portWS = value}
            if (key == "TCP port"){tcpPort = value}
            if (key == "HID"){hid = value}
            if (key == "Alias"){alias = value}
            if (key == "HID"){hid = value}
            if (key == "Leshan endpoint state") {leshanEndpointState = value}
            if (key == "Unique session UUID") {uuid = value}
            if (key == "Custom name") {customName = value}
            if (key == "Send status request") {sendStatusRequest = (value === "True") ? "on" : "off"}
        }
        document.getElementById('wsLink').innerHTML = `ws://${LANIP}:${portWS}`;
        document.getElementById('tcpPort').innerHTML = tcpPort;
        document.getElementById('tcpIP').innerHTML = LANIP;
        document.getElementById('leshan_button').href = `http://${leshanIP}:${leshanPort}`;
        document.getElementById('leshan_button').target = "_blank";
        document.getElementById('customName').innerHTML = `(${customName})`;

        // Handle BLE container info data
        eel.getSessionData("connectedDeviceMac")(function(data) {
            if (data == null) {
                document.getElementById('BLEcontainer').style.display  = "none";
            }
            else {
                // Inherited UUID from device is more than 8 characters
                if (uuid.length > 8 ){
                    document.getElementById('leshan_button').href = `http://${leshanIP}:${leshanPort}/#/clients/${uuid}/3`;
                    document.getElementById('BLEcontainer').style.display  = "block";
                    document.getElementById('EndpointA').innerText = uuid;
                    document.getElementById('EndpointA').href = `http://${leshanIP}:${leshanPort}/#/clients/${uuid}/3`;
                    document.getElementById('EndpointA').target = "_blank";
                    document.getElementById('Endpoint').style.display = "block";
                }
                if (hid) {
                    document.getElementById('BLEcontainer').style.display  = "block";
                    document.getElementById('HIDA').innerText = hid;
                    document.getElementById('HID').style.display = "block";
                }
                if (alias) {
                    document.getElementById('BLEcontainer').style.display  = "block";
                    document.getElementById('AliasA').innerText = alias;
                    document.getElementById('Alias').style.display = "block";
                }
                if (leshanEndpointState == "True") {
                    document.getElementById('LeshanA').innerText = `Connected to Leshan (with regularly status requests ${sendStatusRequest})`;
                    document.getElementById('LeshanA').style.color = "green";
                }
                else if (leshanEndpointState == "False") {
                    document.getElementById('LeshanA').innerText = "Not connected to Leshan";
                    document.getElementById('LeshanA').style.color = "red";
                }
                else if (leshanEndpointState == "Retrieving") {
                    document.getElementById('LeshanA').innerText = "Retriving endpoint status from Leshan...";
                    document.getElementById('LeshanA').style.color = "orange";
                }
            }
        });
    } catch (error) {
        console.error('Error fetching session data:', error);
    }

    // Config:
    CONFIG = {
      LANIP: LANIP, // SBLETS outside LAN address
      //portLeshan: 8080, // Leshan server port
      //portCors: 8083, // Cors-anywhere port (optional)
      portWS: portWS // SBLETS websocket port
    };

    updateNavbar();
}

// On website load fetch info
document.addEventListener('DOMContentLoaded', fetchInfo);

// Controls the visibility of the loader icon for the HAPP device finder service(1 = on)
eel.expose(controlLoader);
function controlLoader(mode){
    var loaderElement = document.getElementById('loader');
    var deviceList = document.getElementById('recogDevices');

    if (mode == 1){
        loaderElement.style.visibility = "visible";
        //console.log("loader visible")
    }
    else if (mode == 0){
        deviceList.style.visibility = "visible";
        loaderElement.style.visibility = "hidden";
        //console.log("loader hidden")
    }
}

// triggerSearch is used to start a search for HAPP devices in find.py (HAPP Device Finder)
document.getElementById('triggerSearch').addEventListener('submit', function(event) {
    event.preventDefault();
    eel.startSearch();
    document.getElementById('recogDevices').style.visibility = "hidden";
    document.getElementById("foundDevices").innerHTML = "";
    document.getElementById('log_HAPPfinder').innerHTML = "";
});

// Send custom CMD with Websocket
document.getElementById('customCMDForm').addEventListener('submit', function(event) {
    event.preventDefault();

    var cmd = document.getElementById('customCMD').value;

    sendCustomCommand(cmd)
});

function sendCustomCommand(cmd) {
    document.getElementById('rawResponse').innerText = `Command ${cmd} in queue...`;

    // Make a correct bytearray string
    const cmdParts = cmd.split('/');
    const byteArray = new Uint8Array(cmdParts.length);

    for (let i = 0; i < cmdParts.length; i++) {
        byteArray[i] = parseInt(cmdParts[i], 16);
    }

    putRLog(`main.js: Sending command ${byteArray} to WebSocket`);
    connectToSocket(byteArray)
}

// For find.py to print HAPP devices with button on GUI that can be used to connect with the device easy
eel.expose(addNewDevice);
function addNewDevice(mac, uuid, NTC, DNC, rssi, alias, key) {
    var deviceList = document.getElementById("foundDevices");

    var newElement = document.createElement("div");
    newElement.innerHTML = `<a style="display: inline-block;" id=${uuid}>${mac}: ${uuid}, NTC: ${NTC}, DNC: ${DNC}, ${rssi} dBm <strong id='aliasFor=${uuid}'>${alias}</strong> <strong id='keyFor=${uuid}'>${key}</strong>  <button class="easyConnectButton" onclick="connectDeviceToGW('${mac}'); showPage('easyConnect')">Connect</button>
        <details>
            <summary>Options</summary>
            <input placeholder="New alias" type="text" id="newAliasFor=${uuid}" style="max-width: 100px;" />
            <button class="easyConnectButton" style="margin-left: 0px; background-color: rgba(39, 39, 39, 0.8); box-shadow: none;" onclick="writeNewAlias('${uuid}');">Save</button>
            <br>
            <input placeholder="New key" type="text" id="newKeyFor=${uuid}" style="max-width: 500px;" />
            <button class="easyConnectButton" style="margin-left: 0px; background-color: rgba(39, 39, 39, 0.8); box-shadow: none;" onclick="writeNewKey('${uuid}');">Save</button>
        </details>
        <br>
    </a>`;
    deviceList.appendChild(newElement);
}

eel.expose(addNewSBLETS);
function addNewSBLETS(name, serverAccess, endpoint, ip, port, version, timestamp) {
    var serverAccessString = ""

    var deviceList = document.getElementById("sbletsServers");
    var endpointField = document.getElementById(`endpointOnSblets=${endpoint}`);

    if (serverAccess == "True") {
        serverAccessString = "(Public)";
    }
    else {
        serverAccessString = "(Private)";
    }

    // If not already shown on frontend
    if (endpointField === null) {
        var newElement = document.createElement("div");
        newElement.setAttribute("id", timestamp)
        newElement.innerHTML = `<a style="display: inline-block;" id=endpointOnSblets=${endpoint}><strong>${endpoint} (${name})</strong> registered to SBLETS version ${version} on:&nbsp;<a href="http://${ip}:${port}" target="_blank">http://${ip}:${port}</a> ${serverAccessString}</a>`;
        deviceList.appendChild(newElement);
    }
    // Update timestamp only
    else {
        endpointField.parentNode.setAttribute("id", timestamp)
    }
}

// Real time minimal log in Info section (Not the same as addToLog which has multiple log boxes)
eel.expose(putRLog);
function putRLog(text) {
    let currentDate = new Date();

    // Add date before log string
    // YYYY-MM-DD
    let date = currentDate.getFullYear() + '-' +
               String(currentDate.getMonth() + 1).padStart(2, '0') + '-' +
               String(currentDate.getDate()).padStart(2, '0');

    // HH:MM:SS
    let time = String(currentDate.getHours()).padStart(2, '0') + ':' +
               String(currentDate.getMinutes()).padStart(2, '0') + ':' +
               String(currentDate.getSeconds()).padStart(2, '0');

    let dateTime = date + ' ' + time + ' |  ';
    var infoBox = document.getElementById('minimalLog');
    infoBox.innerHTML += dateTime + text + '<br>';
}

// This upload form is used by Models Updater to send xlsx file from html to python
document.getElementById('uploadForm').addEventListener('submit', function(event) {
    event.preventDefault();

    var fileInput = document.getElementById('fileInput'); // Should be xlsx file
    var file = fileInput.files[0];

    if (file) {
        var reader = new FileReader();
        reader.onload = function(event) {
            var fileData = event.target.result;
            eel.uploadFile(file.name, fileData)(function(response) {
                document.getElementById('response_modelGen').innerText = response;
            });
        };
        reader.readAsDataURL(file);
    } else {
        document.getElementById('response_modelGen').innerText = 'Please choose a file to upload.';
    }
});

// Write new alias to backend
function writeNewAlias(uuid) {
    newAlias = "";
    var newAlias = document.getElementById('newAliasFor=' + uuid).value;
    var currentAlias = document.getElementById('aliasFor=' + uuid);

    eel.addAlias(uuid, newAlias);

    currentAlias.innerHTML = newAlias;
}

// Write new key to backend
function writeNewKey(uuid) {
    newKey = "";
    var newKey = document.getElementById('newKeyFor=' + uuid).value;
    var currentKey = document.getElementById('keyFor=' + uuid);

    eel.addKey(uuid, newKey);

    currentKey.innerHTML = newKey;
}

// Used by websocket timeout function
var timeout;
var closedDueToTimeout;

// To be used for showing connected to device message, but it can also be used to display status message in that field if mac is false
eel.expose(changeConnectStatus);
function changeConnectStatus(msg, mac = false){
    // connectStatus is the status field on Connect page
    // barConnectStatus is the status field on the navigation bar of the website
    // Ble container is located on the info page and holds HID and name

    if (mac) {
        document.getElementById('connectStatus').innerText = `Connected to ${msg}`;
        document.getElementById('barConnectStatus').innerText = `Connected to ${msg}`;
        document.getElementById('barConnectStatus').classList.remove("barConnectStatus_red");
        document.getElementById('barConnectStatus').style.display  = "block"; // Background is green by default when visible if not other class
    }
    // Hide bar status if device is disconnected
    else if (msg == "Disconnected") {
        document.getElementById('connectStatus').innerText = msg;
        document.getElementById('barConnectStatus').style.display  = "none"; // Background is green by default when visible if not other class
        document.getElementById('BLEcontainer').style.display  = "none";
        document.getElementById('LeshanA').innerText = "Not connected to Leshan";
        document.getElementById('LeshanA').style.color = "red";
    }
    else if (msg == "Connection lost") {
        document.getElementById('connectStatus').innerText = msg;
        document.getElementById('barConnectStatus').innerText = `${msg}`;
        document.getElementById('barConnectStatus').classList.add("barConnectStatus_red");
        document.getElementById('barConnectStatus').style.display  = "block"; // Background is green by default when visible if not other class
        document.getElementById('BLEcontainer').style.display  = "none";
        document.getElementById('LeshanA').innerText = "Not connected to Leshan";
        document.getElementById('LeshanA').style.color = "red";
    }
    // Other msg received
    else {
        document.getElementById('connectStatus').innerText = msg;

        // Even if message is not "Disconnected" the device can still be disconnected
        eel.getSessionData("connectedDeviceMac")(function(data) {
            if (data == null) {
                document.getElementById('barConnectStatus').style.display  = "none"; // Background is green by default when visible if not other class
                document.getElementById('BLEcontainer').style.display  = "none";
            }
        });
    }

    // If width of barConnectStatus changed navigation bar width
    updateNavbar()
}

// On website load fetch info
document.addEventListener('DOMContentLoaded', function(){

    // On new website load show stored status
    eel.getSessionData("connectedDeviceMac")(function(data) {
        if (data !== null) {
            changeConnectStatus(data, true);
        }
        else {
            eel.getSessionData("connectStatusCode")(function(data) {
                if (data !== null) {
                     if (data == 4) {
                        changeConnectStatus("Error, check log!");
                    }
                    else if (data == 5) {
                        changeConnectStatus("Connection lost");
                    }
                    else if (data == 6) {
                        changeConnectStatus("Connection lost, failed to register to Leshan!");
                    }
                } else {
                    changeConnectStatus("unknown");
                }
            });
        }
    });
});

// Controls what page in the SPA application should show
function showPage(pageId) {
    var pages = document.getElementsByClassName('page');
    var navButtons = document.getElementsByClassName('navButton');
    var pageButton = pageId + '_button';

    for (var i = 0; i < pages.length; i++) {
        pages[i].style.display = 'none';
    }

    for (var i = 0; i < navButtons.length; i++) {
        navButtons[i].classList.remove('active');
    }

    document.getElementById(pageId).style.display = 'block';
    var pageButton = pageId + '_button';
    document.getElementById(pageButton).classList.add('active');

}

// Send MAC address to websocket server (Form from connect or easy connect)
document.getElementById('macForm').addEventListener('submit', async function(event) {
    event.preventDefault();
    mac = document.getElementById('macAddress').value;

    connectDeviceToGW(mac);
});

// Generate a bytearray string with command that tells SBLETS to connect device to GW
function connectDeviceToGW(mac) {
    const ESC = 0x1B;
    const STX = 0x02;
    const ETX = 0x03;
    const ESCAPE_STX = 0x82;
    const ESCAPE_ETX = 0x83;
    const ESCAPE_ESCAPE = 0x9B;

    document.getElementById('connectStatus').innerText = "Connect command in queue...";
    const macParts = mac.split(':');
    const macByteArrayRaw = new Uint8Array(macParts.map(part => parseInt(part, 16)));

    var macByteArray = [];

    // Check for any reserved values and replace with escape
    for (let byte of macByteArrayRaw) {
        if (byte === STX) {
            macByteArray.push(ESC, ESCAPE_STX);
        } else if (byte === ETX) {
            macByteArray.push(ESC, ESCAPE_ETX);
        } else if (byte === ESC) {
            macByteArray.push(ESC, ESCAPE_ESCAPE);
        } else {
            macByteArray.push(byte);
        }
    }

    const prefix = new Uint8Array([0x02, 0x0E]);
    const suffix = new Uint8Array([0x05, 0x03]);

    const byteArray = new Uint8Array(prefix.length + macByteArray.length + suffix.length);
    byteArray.set(prefix, 0);
    byteArray.set(macByteArray, prefix.length);
    byteArray.set(suffix, prefix.length + macByteArray.length);
    putRLog(`main.js: Sending MAC Address ${byteArray} to WebSocket`);

    connectToSocket(byteArray, "mac", mac);
}

// Timeout for websocket
function resetTimeout(socket) {
    clearTimeout(timeout);
    timeout = setTimeout(() => {
        console.log('Timeout reached, closing WebSocket');
        closedDueToTimeout = true;
        socket.close();
    }, 65000); // Time before timeout
}

// Indicates if a status response has been successfully received
var websocketResponse;

// Sends request to websocket
function connectToSocket(byteArray, cmd, stringMsg = null){

    socket = new WebSocket(`ws://${CONFIG.LANIP}:${CONFIG.portWS}`);
    //console.log(`Using websocket: ws://${CONFIG.LANIP}:${CONFIG.portWS}`);
    socket.binaryType = 'arraybuffer';
    websocketResponse = false;

    socket.onopen = function (event) {
        console.log('WebSocket connection opened');

        if (cmd == "mac") {
            document.getElementById('connectStatus').innerText = `Connecting to ${stringMsg}...`;
        }
        else {
           document.getElementById('rawResponse').innerText = `Sending ${byteArray} to WebSocket...`;
        }
        socket.send(byteArray);
    };

    socket.onmessage = async function (event) {
        var returnData = event.data.toString();
        document.getElementById('rawResponse').innerText = returnData;
        console.log('Received from server: ', returnData);
        websocketResponse = true;
        clearTimeout(timeout);
        socket.close();
    };

    socket.onclose = function (event) {
        var returnData = new Uint8Array(event.data);
        console.log('Received from server: ', event);
        console.log('WebSocket connection closed');
        if (closedDueToTimeout){
            document.getElementById('connectStatus').innerText = "Connection closed, timeout reached"
        }
        else if (!(websocketResponse)) {
            document.getElementById('connectStatus').innerText = "Connection closed"
        }
    };

    socket.onerror = function (event) {
        console.error('WebSocket error: ', event);
        resetTimeout(socket);
        document.getElementById('connectStatus').innerText = "error";
    };
}

// Used by "Update Leshan Models" to download generated files to users browser
eel.expose(download);
function download(filename, text) {
  var element = document.createElement('a');
  element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(text));
  element.setAttribute('download', filename);

  element.style.display = 'none';
  document.body.appendChild(element);

  element.click();

  document.body.removeChild(element);
}

// Check SBLETS status every 1 seconds
const checkServerStatus = setInterval(async function() {
   try {
       if (eel._websocket && eel._websocket.readyState === WebSocket.OPEN) {
           var status = await eel.getStatus("websocket")();
           //console.log("status is", status);

           // Change the color of the logo text depening on state
           if (status == "Ready") {
               document.getElementById('logoText').style.color = "white";
           }
           else if (status == "Busy") {
               document.getElementById('logoText').style.color = "yellow";
           }
           else {
               document.getElementById('logoText').style.color = "red";
           }
       }
       // If eel is unreachable application is offline
       else{
        document.getElementById('logoText').style.color = "red";
        clearInterval(checkServerStatus);
        document.getElementById('ncpsTitle').style.display = "none";
        document.getElementById('ncps').innerHTML = "";
        document.getElementById('infoDisplay').innerHTML = "<strong>Server status:</strong> Terminated <br><br>";
        document.getElementById('connectStatus').innerText = "Server terminated";
        document.getElementById('barConnectStatus').style.visibility  = "hidden";
        document.getElementById('BLEcontainer').style.display  = "none";
        alert("Lost connection to server, please reload application!");
        throw new Error("Lost connection to server!");
       }
   } catch (error) {
       console.error("Error fetching status:", error);
       document.getElementById('logoText').style.color = "red";
   }

    // Remove offline SBLETS servers by comparing timestamps (On SBLETS network page)
    var deviceList = document.getElementById("sbletsServers");
    var children = deviceList.getElementsByTagName("div");
    var elements = new Array(children.length);
    var arrayLength = children.length;
    for (var i = 0; i < arrayLength; i++) {
        var registeredTimestamp = children[i].getAttribute("id");
        var validTimestamp = (Date.now() / 1000).toFixed(6) - 21;
        if (registeredTimestamp < validTimestamp) {
            children[i].style.color = "red";
        }
    }

}, 1000);

// Tell frontend to update visual info
eel.expose(pingFrontend);
function pingFrontend() {
    //console.log("Frontend ping detected");
    fetchInfo();
}

const dropdownButton = document.getElementById('dropdown_button');

function updateNavbar() {

    const dropdownButton = document.getElementById('dropdown_button');

    const navbarItemsParent = document.getElementById('navbar_items');
    const dropdownItemsParent = document.getElementById('dropdown_items');

    const navbarWidth = (navbarItemsParent.clientWidth - 60); // Subtract padding
    //console.log("Navbar width: ");
    //console.log(navbarWidth);

    const navbarItems = Array.from(navbarItemsParent.children);
    var dropdownItems = Array.from(dropdownItemsParent.children);
    const lastDropdownItem = dropdownItemsParent.lastElementChild;

    const moreElementWidth = document.getElementById('dropdown_button').clientWidth; // Width of "More" element in navbar
    var totalWidth = 0;
    var moveToDropdownItems = [];

    // Check if item to wide for main navbar
    navbarItems.forEach(item => {
        totalWidth += item.clientWidth; // To compensate for largest navigation item
        //console.log("Total width: ");
        //console.log(totalWidth);
        if (totalWidth > navbarWidth) {
            //console.log(item)
            moveToDropdownItems.push(item);
        }
    });

    // Get the dataset order for the last item in main navbar to insure correct display order again
    const lastItem = navbarItemsParent.lastElementChild;
    var lastItemOrderNumber = 0;

    if (lastItem) {
        lastItemOrderNumber = lastItem.dataset.order;
        //console.log('Data-order of the rightmost item:', lastItemOrderNumber);
    }

    var moveToNavbarItems = [];
    // Check if a dropdown item fits in the width of the main navbar
    for (let i = 0; i < dropdownItems.length; i++) {
        let item = dropdownItems[i];
        if (((totalWidth + (item.clientWidth * 1)) < navbarWidth) && ((item.dataset.order == (Number(lastItemOrderNumber) + 1)))) { // To compensate for largest navigation item
            moveToNavbarItems.push(item);
        }
    }

    allItems = moveToDropdownItems.concat(moveToNavbarItems);

    // Sort items according to data-order tag
    allItems.sort((a, b) => {
        return Number(b.dataset.order) - Number(a.dataset.order);
    });

    // Go through all items and place them in correct navbar
    allItems.forEach(item => {
        if (moveToDropdownItems.includes(item)) {
            if (!dropdownItemsParent.contains(item)) {
                dropdownItemsParent.appendChild(item);
            }
        }
        else {
            navbarItemsParent.appendChild(item);
        }

    });

    dropdownItems = Array.from(dropdownItemsParent.children);

    if (dropdownItems.length > 0) {
        dropdownButton.style.display = "block"
    }
    else {
        dropdownButton.style.display = "none"
    }
}

dropdownButton.addEventListener('click', () => {
    const dropdownItemsParent = document.getElementById('dropdown_items');

    const isOpen = dropdownItemsParent.style.visibility === 'visible';
    dropdownItemsParent.style.visibility = isOpen ? 'hidden' : 'visible';

    dropdownButton.classList.toggle('open');
});

// Update navbar on resize
window.addEventListener('resize', updateNavbar);

// Update navbar after application load
document.addEventListener('load', updateNavbar);

