# ============================================================
# MQTT to REST API Bridge
# ------------------------------------------------------------
# This script acts as a middleware bridge between an MQTT
# message broker and a REST API. It subscribes to MQTT topics
# for agricultural ("agri") and water ("water") sensor states,
# stores the latest payloads in memory, and exposes them via
# HTTP endpoints using Flask.
# ============================================================

import json          # For parsing JSON payloads received from MQTT messages
import threading     # For running the MQTT loop concurrently with Flask server
from flask import Flask, jsonify          # Flask web framework and JSON response helper
import paho.mqtt.client as mqtt          # Paho MQTT client library for broker communication

# ============================================================
# Flask App Initialization
# ------------------------------------------------------------
# Creates the Flask web application instance. This will serve
# the REST API endpoints on a local HTTP server.
# ============================================================
app = Flask(__name__)

# ============================================================
# In-Memory Data Store
# ------------------------------------------------------------
# A shared dictionary that holds the latest MQTT payloads for
# each topic category. This acts as a simple real-time cache:
#   - "agri"  : Latest state received from "agri/state" topic
#   - "water" : Latest state received from "water/state" topic
#
# NOTE: This is not thread-safe by default. For production use,
# consider using threading.Lock() when reading/writing to avoid
# race conditions between the MQTT thread and Flask thread.
# ============================================================
data_store = {
   "agri": {},
   "water": {}
}

# ============================================================
# MQTT Broker Configuration
# ------------------------------------------------------------
# Hostname or IP address of the MQTT broker to connect to.
# "localhost" assumes the broker (e.g., Mosquitto) is running
# on the same machine as this script.
# Change this to the broker's IP/hostname for remote brokers.
# ============================================================
BROKER = "localhost"

# ============================================================
# MQTT Callback — on_connect
# ------------------------------------------------------------
# Triggered automatically when the MQTT client successfully
# establishes a connection to the broker.
#
# Parameters:
#   client     : The MQTT client instance
#   userdata   : User-defined data (not used here)
#   flags      : Response flags from the broker
#   rc         : Result/return code (0 = connection successful)
#   properties : MQTT v5 properties (optional, default None)
#
# Subscribes to two topics on successful connection:
#   - "agri/state"  : Receives agricultural sensor/device state
#   - "water/state" : Receives water system sensor/device state
# ============================================================
def on_connect(client, userdata, flags, rc, properties=None):
   print("Connected to MQTT")
   client.subscribe("agri/state")    # Subscribe to agricultural state updates
   client.subscribe("water/state")   # Subscribe to water system state updates

# ============================================================
# MQTT Callback — on_message
# ------------------------------------------------------------
# Triggered automatically whenever a message is received on
# any subscribed topic.
#
# Parameters:
#   client   : The MQTT client instance
#   userdata : User-defined data (not used here)
#   msg      : The received message object containing:
#                - msg.topic   : The topic the message arrived on
#                - msg.payload : The raw bytes of the message body
#
# Workflow:
#   1. Decode the raw bytes payload to a UTF-8 string
#   2. Parse the JSON string into a Python dictionary
#   3. Store the parsed data into the appropriate key in data_store
#   4. Print the topic and payload for real-time console logging
#
# NOTE: If the payload is not valid JSON, json.loads() will raise
# a JSONDecodeError. Add try/except in production for resilience.
# ============================================================
def on_message(client, userdata, msg):
   payload = json.loads(msg.payload.decode())   # Decode bytes → string → parse JSON to dict

   if msg.topic == "agri/state":
       data_store["agri"] = payload             # Overwrite with latest agricultural state
   elif msg.topic == "water/state":
       data_store["water"] = payload            # Overwrite with latest water system state

   print(msg.topic, payload)                    # Log received topic and data to console

# ============================================================
# MQTT Client Thread Function — mqtt_loop
# ------------------------------------------------------------
# Initializes, configures, and starts the MQTT client in a
# blocking loop. Designed to run in a background thread so it
# doesn't block the Flask HTTP server.
#
# Steps:
#   1. Instantiate a new Paho MQTT Client
#   2. Attach the on_connect and on_message callback functions
#   3. Connect to the broker at BROKER address, port 1883,
#      with a keepalive interval of 60 seconds
#      - Port 1883 : Standard unencrypted MQTT port
#      - Keepalive  : Seconds between ping packets to keep the
#                     connection alive when idle
#   4. Start loop_forever() — a blocking network loop that
#      handles reconnections, message dispatching, and heartbeats
# ============================================================
def mqtt_loop():
   client = mqtt.Client()                  # Create a new MQTT client instance
   client.on_connect = on_connect          # Register the connection callback
   client.on_message = on_message          # Register the message received callback
   client.connect(BROKER, 1883, 60)       # Connect to broker (host, port, keepalive)
   client.loop_forever()                   # Start blocking network loop (handles all MQTT I/O)

# ============================================================
# Flask REST API — GET /agri
# ------------------------------------------------------------
# HTTP GET endpoint that returns the latest agricultural state.
#
# Route   : /agri
# Method  : GET (default)
# Response: JSON representation of data_store["agri"]
#
# Returns an empty JSON object {} if no MQTT message has been
# received yet for the "agri/state" topic.
# ============================================================
@app.route("/agri")
def agri():
   return jsonify(data_store["agri"])      # Serialize and return agri state as JSON response

# ============================================================
# Flask REST API — GET /water
# ------------------------------------------------------------
# HTTP GET endpoint that returns the latest water system state.
#
# Route   : /water
# Method  : GET (default)
# Response: JSON representation of data_store["water"]
#
# Returns an empty JSON object {} if no MQTT message has been
# received yet for the "water/state" topic.
# ============================================================
@app.route("/water")
def water():
   return jsonify(data_store["water"])     # Serialize and return water state as JSON response

# ============================================================
# Application Entry Point
# ------------------------------------------------------------
# Runs only when the script is executed directly (not imported).
#
# Startup sequence:
#   1. Launch the MQTT client in a background daemon thread
#      - daemon=True (implied by Thread default) means this thread
#        won't block program exit if Flask shuts down
#   2. Start the Flask development server
#      - host="127.0.0.1" : Only accessible locally (loopback).
#        Change to "0.0.0.0" to expose on all network interfaces.
#      - port=5000        : Standard Flask development port
#
# Architecture: Two concurrent execution paths
#   [Thread 1 - Main]   : Flask HTTP server handles REST requests
#   [Thread 2 - MQTT]   : Paho loop listens for broker messages
# ============================================================
if __name__ == "__main__":
   threading.Thread(target=mqtt_loop).start()   # Start MQTT listener in a background thread
   app.run(host="127.0.0.1", port=5000)         # Start Flask REST API server on localhost:5000
