import json
import logging
import os
import tempfile
import time
from collections import namedtuple
from threading import Event
import ssl

import paho.mqtt.client as mqtt
import requests

logging.basicConfig(format='%(asctime)s %(module)-8s %(funcName)-10s %(levelname)-8s %(message)s',
                    level=logging.INFO,
                    datefmt='%Y-%m-%d %H:%M:%S')
log = logging.getLogger(__name__)


class Landroid(object):
    _username = None
    _api_user = None
    _mqtt_endpoint = None
    _mqtt_topic_in = None
    _mqtt_topic_out = None
    _api_product_items = None
    _api_boards = None
    _api_products = None
    _mower_product = None  # holds the current mower from _api_products
    _api_certificate = None
    _status = None  # type: LandroidStatus
    _mqtt_client = None
    _cachedir = None
    _cache = {}
    _refreshToken = None
    _expiresAt = 0  # Unix timestamp
    
    # Global Identity Endpoint (Consolidated from regional id.eu.worx.com)
    AUTH_URL = "https://id.worx.com/oauth/token"
    API_BASE_URL = "https://api.worxlandroid.com/api/v2/"
    
    # This Client ID remains the standard for the 2026 Positec ecosystem
    WORX_CLIENT_ID = "150da4d2-bb44-433b-9429-3773adc70a2a" 
    _user_id = None
    _mower_uuid = None
    _sn = None

    def __init__(self):
        """
        Class to communicate with the Landroid cloud using REST for user information and MQTT for getting status
        updates and send them to the mower
        """
        self._statuscallback = None
        self._eventmessage = Event()
        self._eventconnect = Event()

    def connect(self, username, password):
        """
        Connect to the cloud with the given credentials.

        Updated connect logic for the 2026 Global API

        :param username: Username for the cloud login
        :param password: Password for the login
        :return: None
        """
        self._username = username
        self._cachedir = os.path.join(tempfile.gettempdir(), "landroidcc", self._username)
        self._initcache()
        
        # 1. Authenticate (Global id.worx.com)
        self._api_authentificate(username, password)

        # 2. Skip users/me (avoids 405) and go straight to product-items.
        # Ensure your _apicall_rest handles the ?status=1 query param.
        self._api_product_items = self._apicall_rest("product-items?status=1")
        
        if not self._api_product_items:
            log.error("No mowers found for this account.")
            return

        log.debug("Product: %s", self._api_product_items)

        try:
            self._api_user = self._apicall_rest("users/me")
        except requests.exceptions.HTTPError as e:
            log.warning("Endpoint 'users/me' returned 404 '%s'. Falling back to Unknown.", str(e))

            try:
                self._api_user = self._apicall_rest("api/v1/users/me")
            except requests.exceptions.HTTPError as e:
                log.warning("Endpoint 'users/me' returned 404 '%s'. Falling back to Unknown.", str(e))
                self._api_user = "Unknown"


        # 3. Extract the MQTT endpoint from the product item itself
        # In the 2026 API, this is the authoritative source for the broker URL
        self._mqtt_endpoint = self._api_product_items[0].get("mqtt_endpoint")
        
        # 4. Map the topics
        self._mqtt_topic_out = self._api_product_items[0]["mqtt_topics"]["command_out"]
        self._mqtt_topic_in = self._api_product_items[0]["mqtt_topics"]["command_in"]
        
        # 5. Continue with metadata, handling 404s for potentially deprecated endpoints
        try:
            self._api_boards = self._apicall_rest("boards")
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                log.warning("Endpoint 'boards' returned 404. Falling back to empty list.")
                self._api_boards = []
            else:
                raise

        try:
            self._api_products = self._apicall_rest("products")
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                log.warning("Endpoint 'products' returned 404. Falling back to empty list.")
                self._api_products = []
            else:
                raise        
        product_id = self._api_product_items[0]["product_id"]
        for product in self._api_products:
            if product["id"] == product_id:
                self._mower_product = product
                break

        # print(json.dumps(self._api_product_items, indent=2))
        # print(json.dumps(self._mower_product, indent=2))
        # Store details
        self._user_id = self._api_product_items[0].get("user_id")
        self._sn = self._api_product_items[0].get("serial_number")
        self._mower_uuid = self._api_product_items[0].get("uuid")
        
        log.debug("UserID: %s, Serial number: %s, UUID: %s", 
            self._user_id, self._sn, self._mower_uuid)

        self._writecache()
        self._connectmqtt()
       
    def disconnect(self):
        """
        Disconnects from the cloud

        :return: None
        """
        self._mqtt_client.disconnect()

    def start(self):
        """
        Sent the mower the command to start mowing

        :return: None
        """
        self._send_command('{"cmd": 1}')
        log.info("Command sent: Start Mowing")

    def pause(self):
        """
        Sent the mower the command to pause mowing

        :return: None
        """
        self._send_command('{"cmd": 2}')
        log.info("Command sent: Pause Mowing")

    def go_home(self):
        """
        Sent the mower the command to go home mowing

        :return: None
        """
        self._send_command('{"cmd": 3}')
        log.info("Command sent: Go Home")

    def _send_command(self, cmd):
        self._mqtt_client.publish(self._mqtt_topic_in, cmd)

    def _connectmqtt(self):
        # Callback for connect
        def on_connect(client, userdata, flags, rc):
            log.debug("MQTT Connected with result code " + str(rc))
            if rc == 0:
                client.subscribe(self._mqtt_topic_out)
                log.info("Successfully connected to the cloud via WebSockets")
                self._eventconnect.set()
            else:
                log.error(f"MQTT Connection failed with return code {rc}")

        # The callback for when a PUBLISH message is received from the server.
        def on_message(client, userdata, msg):
            log.debug("MQTT Msg Received: " + msg.topic + " " + str(msg.payload))
            payload = msg.payload.decode('utf-8') if isinstance(msg.payload, (bytes, bytearray)) else msg.payload
            status = LandroidStatus(payload)
            self._status = status
            self._eventmessage.set()
            if self._statuscallback:
                self._statuscallback(status)

        def on_log(client, userdata, level, buf):
            log.debug("MQTT Library Log: {}".format(buf))

        # --- 2026 JWT AUTH LOGIC ---
        # 1. Precise token splitting (Ensure no leading/trailing whitespace)
        normalized_token = self._accessToken.replace('_', '/').replace('-', '+')
        tok = normalized_token.split('.')        
        jwt_payload = f"{tok[0]}.{tok[1]}"
        signature = tok[2]

        # 2. Strict Header Keys (Check case sensitivity)
        custom_headers = {
            "x-amz-customauthorizer-name": "com-worxlandroid-customer",
            "x-amz-customauthorizer-signature": signature,
            "jwt": jwt_payload
        }

        # 3. Mirror the WorxLandroid openHAB Java Client ID exactly
        # Format: WX/USER/<user_id>/openhab/<product_uuid>
        # Note: 'openhab' is literal here, as seen in the Java MQTT_USERNAME
        client_id = f"WX/USER/{self._user_id}/openhab/{self._mower_uuid}"
        
        self._mqtt_client = mqtt.Client(client_id=client_id, transport="websockets", userdata=self)
        
        # 4. Set Clean Session to False (Mirroring Java .withCleanSession(false))
        self._mqtt_client.ws_set_options(path="/mqtt", headers=custom_headers)
        self._mqtt_client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2)
        
        # 5. Username is required for the authorizer to trigger
        self._mqtt_client.username_pw_set("openhab")

        self._mqtt_client.on_connect = on_connect
        self._mqtt_client.on_message = on_message
        self._mqtt_client.on_log = on_log

        log.info(f"Connecting to {self._mqtt_endpoint} on port 443...")
        self._mqtt_client.connect(self._mqtt_endpoint, 443, keepalive=300)
        
        self._mqtt_client.loop_start()
        
        if not self._eventconnect.wait(30):
            # If it times out, check the 'on_log' output in your terminal
            log.error("MQTT connection timed out. Check MQTT Library Logs above.")
            
        return self._status

    def set_statuscallback(self, func):
        """
        Sets a callback function which will be called for any status update from the mower::

          def callback(status):
            # type: (LandroidStatus) -> None
            print (status)

          landroid = Landroid()
          landroid.connect("", "")
          landroid.set_statuscallback(callback)

        :param func: The callback
        :return: None
        """
        self._statuscallback = func

    def get_status(self, refresh=True):
        """
        Returns the last retrieved status from the mower. If refresh is True an update is
        requested from the mower and the call will block until an update is received.

        Once connected the status will automatically updated once the mower sent an automatic
        update message. This happens every 2-15 minutes and for all state changes.

        :param refresh: Force an update or only return the cached last status
        :rtype: LandroidStatus
        :return: The status of the mower.
        """
        if refresh:
            if not self._apicall_mqtt("{}"):
                log.warning("Timeout while trying to get a new status")
                log.info("Status: %s", str(self._status))

        return self._status

    def _apicall_mqtt(self, content, blocking=True):
        log.debug("MQTT call with: '{}'".format(content))
        self._eventmessage.clear()
        self._mqtt_client.publish(self._mqtt_topic_in, content)
        result = True
        if blocking:
            result = self._eventmessage.wait(10)
        log.debug("MQTT call finished")
        return result

    def _initcache(self):
        cachedir = os.path.join(self._cachedir, self._username)
        cachefilename = os.path.join(cachedir, "cache.json")
        if not os.path.isfile(cachefilename):
            return
        with open(cachefilename) as fptr:
            try:
                self._cache = json.load(fptr)
                return
            except ValueError as ve:
                log.debug("Failed to parse cache file: {}".format(ve))

    def _writecache(self):
        cachedir = os.path.join(self._cachedir, self._username)
        if not os.path.isdir(cachedir):
            os.makedirs(cachedir)
        with open(os.path.join(cachedir, "cache.json"), "w") as fptr:
            json.dump(self._cache, fptr)

    def _apicall_rest(self, url, postdata=None, set_headers=True, allow_cached=True):
        if allow_cached and not postdata and url in self._cache:
            log.debug("API Call form Cache: '{}': {}".format(url, self._cache[url]))
            return self._cache[url]

        headers = None
        if set_headers:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"{self._accessTokenType} {self._accessToken}",
                # 2026 Critical Addition: Identification
                "User-Agent": "Landroid/3.33 (com.worxlandroid.customer; build:1234; iOS 17.4.1) Alamofire/5.9.1",
                "X-App-Id": "com.worxlandroid.customer"
            }
        # Apply the Java change for status-inclusive calls if requested
        if url.startswith("api"):
            base = "https://api.worxlandroid.com/"
        else:
            base = self.API_BASE_URL # This is your .../v2/
            
        target_url = base + url
        if url == "product-items":
            target_url += "?status=1"

        if postdata:
            response_plain = requests.post(target_url, json=postdata, headers=headers)
        else:
            response_plain = requests.get(target_url, headers=headers)        

        response_plain.raise_for_status()
        response = response_plain.json()
        log.debug("API Call '{}': {}".format(url, response))
        self._cache[url] = response
        return response

    def _api_authentificate(self, username, password):
        post_json = {
            "username": username,
            "password": password,
            "grant_type": "password",
            "client_id": self.WORX_CLIENT_ID, # Updated
            "type": "app",
            "client_secret": "nCH3A0WvMYn66vGorjSrnGZ2YtjQWDiCvjg7jNxK",
            "scope": "*"
        }
        # Direct call to the new AUTH_URL instead of the v2 API path
        response_plain = requests.post(self.AUTH_URL, json=post_json)
        response_plain.raise_for_status()
        response = response_plain.json()

        self._accessToken = response["access_token"]
        self._refreshToken = response.get("refresh_token")
        self._accessTokenType = response["token_type"]
        # Buffer the expiration by 60 seconds to avoid race conditions
        self._expiresAt = time.time() + int(response.get("expires_in", 3600)) - 60
        
        log.info("Successfully logged in and retrieved refresh token, authenticated via global identity server.")        

    def _refresh_token(self):
        """Refreshes the session using the stored refresh_token"""
        if not self._refreshToken:
            log.error("No refresh token available. Re-authenticating...")
            return # Alternatively, trigger _api_authentificate

        post_json = {
            "grant_type": "refresh_token",
            "refresh_token": self._refreshToken,
            "client_id": self.WORX_CLIENT_ID,
            "client_secret": "nCH3A0WvMYn66vGorjSrnGZ2YtjQWDiCvjg7jNxK",
            "scope": "*"
        }
        
        log.debug("Attempting to refresh access token")
        response_plain = requests.post(self.AUTH_URL, json=post_json)
        response_plain.raise_for_status()
        response = response_plain.json()

        self._accessToken = response["access_token"]
        self._refreshToken = response.get("refresh_token", self._refreshToken)
        self._expiresAt = time.time() + int(response.get("expires_in", 3600)) - 60
        log.info("Access token refreshed successfully")

    def __str__(self):
        if not self._api_user:
            return "API not connected"
        return "landroid info\n" \
               "#############\n" \
               "Name:   {name}\n" \
               "Serial: {serial}\n" \
               "Type:   {code}\n".format(name=self._api_product_items[0]["name"],
                                         serial=self._api_product_items[0]["serial_number"],
                                         code=self._mower_product["code"])


class LandroidStatus(object):
    BatteryStatus = namedtuple("BatteryStatus", "percent,charges,volts,temperature,charging")
    Orientation = namedtuple("Orientation", "heading,pitch,roll")
    Statistics = namedtuple("Statistics", "distance,running,mowing")
    _lastStateDict = {
        0: "Idle",
        1: "Home",
        2: "Start sequence",
        3: "Leaving home",
        4: "Follow wire",
        5: "Searching home",
        6: "Searching wire",
        7: "Mowing",
        8: "Lifted",
        9: "Trapped",
        10: "Blade blocked",
        11: "Debug",
        12: "Remote control",
        30: "Going home",
        32: "Border Cut",
        33: "Searching zone",
        34: "Pause"
    }
    _lastErrorDict = {
        0: "No error",
        1: "Trapped",
        2: "Lifted",
        3: "Wire missing",
        4: "Outside wire",
        5: "Raining",
        6: "Close door to mow",
        7: "Close door to go home",
        8: "Blade motor blocked",
        9: "Wheel motor blocked",
        10: "Trapped timeout",
        11: "Upside down",
        12: "Battery low",
        13: "Reverse wire",
        14: "Charge error",
        15: "Timeout finding home"

    }

    def __init__(self, inputraw):
        self._battery = None
        self._orientation = None
        self._statistics = None

        self._error = None
        self._state = None
        self._updated = None
        self._raw = inputraw  # Raw string as received from the mower
        self._updatestatus(inputraw)

    def get_battery(self):
        """

        :return:
        :rtype: BatteryStatus
        """
        return self._battery

    def get_orientation(self):
        return self._orientation

    def get_statistics(self):
        return self._statistics

    def get_updated(self):
        return self._updated

    def get_error(self):
        """
        Returns the error as string. If there is no error, "No Error" is returned

        :return: The error as text
        :rtype: str
        """
        return self._error

    def get_state(self):
        """
        Returns the state as string

        :return: The state as text
        :rtype: str
        """
        return self._state

    def get_raw(self):
        """
        Returns the status update as received directly from MQTT/mower.

        :return: Raw status message
        :rtype: dict
        """
        return self._raw

    def _updatestatus(self, inputraw):
        self._raw = inputraw
        api_response = json.loads(inputraw)

        self._battery = self.BatteryStatus(api_response["dat"]["bt"]["p"],
                                            api_response["dat"]["bt"]["nr"],
                                            api_response["dat"]["bt"]["v"],
                                            api_response["dat"]["bt"]["t"],
                                            api_response["dat"]["bt"]["c"] != "0")

        self._orientation = self.Orientation(api_response["dat"]["dmp"][2],
                                             api_response["dat"]["dmp"][0],
                                             api_response["dat"]["dmp"][1])

        self._statistics = self.Statistics(api_response["dat"]["st"]["d"],
                                           api_response["dat"]["st"]["wt"],
                                           api_response["dat"]["st"]["b"])

        self._state = self._lastStateDict[api_response["dat"]["ls"]]
        self._error = self._lastErrorDict[api_response["dat"]["le"]]
        self._updated = api_response["cfg"]["tm"] + " " + api_response["cfg"]["dt"]

    def __str__(self):
        return "landroid status\n" \
               "###############\n" \
               "LastUpdate: {updated}\n" \
               "State:      {state}\n" \
               "Error:      {error}\n" \
               "Battery:    {percent}%/{temp}C/{voltage}v" \
               "".format(updated=self._updated, state=self._state, error=self._error,
                         percent=self._battery.percent, temp=self._battery.temperature, voltage=self._battery.volts)
