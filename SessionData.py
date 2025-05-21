class SessionData:
    def __init__(self):
        self.connectedDeviceMac = None
        self.connectedDeviceHID = None
        self.connectedDeviceAlias = None
        self.connectedDeviceIPRID = None
        self.uniqueSessionUUID = None
        self.startupUniqueSessionUUID = None
        self.connectStatusCode = 7
        self.runningGateway = False
        self.lastHAPPScan = None
        self.deviceConnectedToLeshan = "False"
        self.foundSbletsServers = None


sessionData = SessionData()


##### -- STATUS CODES: -- #####
# 0 = Disconnected
# 1 = Connected
# 3 = RFU
# 4 = ERROR
# 5 = Connection lost
# 6 = Connection lost with Leshan registration error
# 7 = Initial state on startup
# 8 = RFU
# 9 = RFU
################################