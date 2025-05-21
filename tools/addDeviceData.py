import configparser
import json
import eel

# Create a ConfigParser object
config = configparser.ConfigParser()

# Read the configuration file
config.read('config.ini')


# Store alias associated with the device IPRID/UUID
@eel.expose
def addAlias(iprid, alias):
    deviceLookupFilePath = (config.get('SBLETS', 'Device lookup path'))
    if deviceLookupFilePath is None: return False

    with open(deviceLookupFilePath, 'r') as jsonData:
        deviceLookupJSON = json.load(jsonData)
        deviceLookupJSON[iprid] = alias
    with open(deviceLookupFilePath, 'w') as jsonData:
        json.dump(deviceLookupJSON, jsonData, indent=4)
    return True


# Store device key that should be pushed to Leshan credentials
@eel.expose
def addKey(iprid, secret):
    deviceSecretsFilePath = (config.get('SBLETS', 'Device secrets path'))
    if deviceSecretsFilePath is None: return False

    with open(deviceSecretsFilePath, 'r') as jsonData:
        deviceSecretsSON = json.load(jsonData)
        deviceSecretsSON[iprid] = secret
    with open(deviceSecretsFilePath, 'w') as jsonData:
        json.dump(deviceSecretsSON, jsonData, indent=4)
    return True
