# ============================================================
# HTTP API to MQTT Publisher Bridge
# ------------------------------------------------------------
# This script acts as a data forwarder/publisher. It periodically
# polls two local HTTP REST APIs (agricultural and water systems),
# fetches their latest state data, and publishes the results to
# an MQTT broker hosted on a remote VPS server.
#
# Data Flow:
#   [Local HTTP APIs] --> [This Script] --> [Remote MQTT Broker]
#
# Both APIs are protected with HTTP Basic Authentication.
# The MQTT broker is publicly accessible via its VPS IP.
# ============================================================

import time                          # For sleep delays between polling cycles
import json                          # For serializing Python dicts to JSON strings before publishing
import requests                      # For making HTTP GET requests to the local REST APIs
import paho.mqtt.client as mqtt      # Paho MQTT client for connecting and publishing to the broker

# ============================================================
# Source API Endpoints
# ------------------------------------------------------------
# These are the local HTTP REST API URLs that provide the
# current state of the agricultural and water systems.
# Both are hosted on localhost (127.0.0.1) at port 18081.
#
#   AGRI_URL  : Returns the current agricultural device/sensor state
#   WATER_URL : Returns the current water system device/sensor state
# ============================================================
AGRI_URL  = "http://127.0.0.1:18081/state"
WATER_URL = "http://127.0.0.1:18081/water"

# ============================================================
# MQTT Broker Configuration
# ------------------------------------------------------------
# The remote MQTT broker hosted on a VPS server.
# Messages published here can be consumed by any subscriber
# connected to this broker (e.g., the Flask bridge server).
#
#   MQTT_HOST   : Public IP address of the VPS running the broker
#   TOPIC_AGRI  : MQTT topic for agricultural state messages
#   TOPIC_WATER : MQTT topic for water system state messages
# ============================================================
MQTT_HOST   = "0.0.0.0"             #Your Destination Server-IP
TOPIC_AGRI  = "agri/state"
TOPIC_WATER = "water/state"

# ============================================================
# HTTP Basic Authentication Credentials
# ------------------------------------------------------------
# Each API endpoint requires its own set of credentials.
# Credentials are passed as (username, password) tuples and
# used by the requests library for HTTP Basic Auth headers.
#
#   auth_agri  : Credentials for the agricultural state API
#   auth_water : Credentials for the water system state API
# ============================================================
auth_agri  = ("unity", "secret123")
auth_water = ("water", "secret123")

# ============================================================
# MQTT Client Setup
# ------------------------------------------------------------
# Initializes the MQTT client using the modern Paho API v2
# callback interface (CallbackAPIVersion.VERSION2).
#
#   client.connect() : Establishes TCP connection to the broker
#                      Args: host, port (1883 = standard MQTT),
#                            keepalive (60s ping interval)
#   client.loop_start(): Starts a background thread that handles
#                        all MQTT network I/O (sending, receiving,
#                        reconnections) without blocking the main loop
# ============================================================
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect(MQTT_HOST, 1883, 60)    # Connect to remote VPS MQTT broker on standard port
client.loop_start()                    # Launch non-blocking background network loop

# ============================================================
# Helper Function — fetch()
# ------------------------------------------------------------
# Makes an authenticated HTTP GET request to the given URL
# and returns the parsed JSON response as a Python dictionary.
#
# Parameters:
#   url  : The full HTTP endpoint URL to request data from
#   auth : A (username, password) tuple for Basic Auth
#
# Returns:
#   dict  : Parsed JSON response body on success
#   None  : If any error occurs (network issue, timeout, bad JSON)
#
# Error Handling:
#   - timeout=3 ensures the request fails fast if the API is
#     unresponsive, preventing the main loop from hanging
#   - The broad Exception catch handles all failure modes:
#     ConnectionError, Timeout, JSONDecodeError, etc.
#   - Returns None on failure so the caller can skip publishing
# ============================================================
def fetch(url, auth):
   try:
       r = requests.get(url, auth=auth, timeout=3)    # GET request with Basic Auth and 3s timeout
       return r.json()                                 # Parse and return JSON body as a dict
   except Exception as e:
       print("Fetch error:", e)                        # Log error details to console for debugging
       return None                                     # Return None to signal fetch failure

# ============================================================
# Main Polling Loop
# ------------------------------------------------------------
# Continuously fetches data from both HTTP APIs and publishes
# the results to their respective MQTT topics on the remote broker.
#
# Loop Cycle per Iteration:
#   1. Fetch agricultural state from AGRI_URL
#      - If successful, serialize to JSON and publish to TOPIC_AGRI
#      - If fetch failed (None), skip publishing silently
#   2. Fetch water system state from WATER_URL
#      - If successful, serialize to JSON and publish to TOPIC_WATER
#      - If fetch failed (None), skip publishing silently
#   3. Sleep for 0 seconds before the next cycle
#      NOTE: time.sleep(0) yields the CPU briefly but effectively
#      runs as fast as possible (no real delay). Change to a
#      positive value (e.g., time.sleep(5)) to reduce API load
#      and broker message frequency in production.
#
# Publishing:
#   - json.dumps() converts the dict payload to a JSON string
#     since MQTT messages must be transmitted as bytes/strings
#   - client.publish() sends the message to the broker topic
#     via the background loop thread started earlier
# ============================================================
while True:
   # ---------- Agricultural State ----------
   agri = fetch(AGRI_URL, auth_agri)          # Poll the agricultural REST API
   if agri:                                    # Only publish if fetch returned valid data
       client.publish(TOPIC_AGRI, json.dumps(agri))   # Serialize dict to JSON string and publish
       print("AGRI -> sent")                           # Confirm successful publish to console

   # ---------- Water System State ----------
   water = fetch(WATER_URL, auth_water)        # Poll the water system REST API
   if water:                                   # Only publish if fetch returned valid data
       client.publish(TOPIC_WATER, json.dumps(water))  # Serialize dict to JSON string and publish
       print("WATER -> sent")                           # Confirm successful publish to console

   time.sleep(0)    # Delay between polling cycles (0 = no delay; increase for rate limiting)
