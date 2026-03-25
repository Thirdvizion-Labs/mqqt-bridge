# MQTT ↔ REST API Bridge — Deployment Guide

A two-server system that polls local HTTP APIs for agricultural and water sensor data, forwards it to a remote MQTT broker, and exposes it back as a REST API via Flask.

---

## Architecture Overview

```
┌─────────────────────┐        MQTT Publish         ┌──────────────────────┐
│   mqqt-publisher.py │ ─────────────────────────►  │   MQTT Broker (VPS)  │
│  (Polling Server)   │                             │   <YOUR_VPS_IP>      │
│                     │                             │   Port: 1883         │
│  Polls:             │                             └──────────┬───────────┘
│  - /state  (agri)   │                                        │
│  - /water  (water)  │                                        │ MQTT Subscribe
└─────────────────────┘                                        ▼
                                                    ┌──────────────────────┐
                                                    │   mqtt-receiver.py   │
                                                    │  (Flask API Server)  │
                                                    │                      │
                                                    │  Exposes:            │
                                                    │  GET /agri           │
                                                    │  GET /water          │
                                                    └──────────────────────┘
```

---

## Project Structure

```
project/
│
├── mqtt-publisher.py        # Polls local HTTP APIs → publishes to MQTT broker
├── mqtt-receiver.py         # Subscribes to MQTT broker → exposes REST API via Flask
└── README.md
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.8+ | Check with `python3 --version` |
| pip | Latest | Check with `pip --version` |
| Mosquitto (MQTT Broker) | Any | Only needed on VPS |
| Network access | — | Publisher needs access to VPS IP |

---

## 1. MQTT Broker Setup (VPS Server)

> Run these steps **on your VPS** at `Destination Server`

### Install Mosquitto

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install -y mosquitto mosquitto-clients

# CentOS / RHEL
sudo yum install -y mosquitto
```

### Configure Mosquitto

```bash
sudo nano /etc/mosquitto/mosquitto.conf
```

Add the following lines:

```conf
listener 1883
allow_anonymous true
```

> **Note:** For production, disable anonymous access and set up username/password authentication using `mosquitto_passwd`.

### Start & Enable the Broker

```bash
sudo systemctl start mosquitto
sudo systemctl enable mosquitto

# Verify it is running
sudo systemctl status mosquitto
```

### Open Firewall Port

```bash
# UFW (Ubuntu)
sudo ufw allow 1883/tcp
sudo ufw reload

# firewalld (CentOS)
sudo firewall-cmd --permanent --add-port=1883/tcp
sudo firewall-cmd --reload
```

---

## 2. Python Environment Setup

> Run these steps on **both machines** (publisher machine and Flask server machine)

### Create a Virtual Environment

```bash
# Navigate to your project folder
cd /path/to/project

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# Linux / macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### Install Dependencies

```bash
pip install flask paho-mqtt requests
```

Or create a `requirements.txt` and install from it:

```bash
# requirements.txt
flask==3.0.3
paho-mqtt==2.1.0
requests==2.32.3
```

```bash
pip install -r requirements.txt
```

### Verify Installation

```bash
python3 -c "import flask, paho.mqtt.client, requests; print('All dependencies OK')"
```

---

## 3. Deploy `publisher.py` (Polling Server)

> This server **polls the local HTTP APIs** and **publishes to the MQTT broker**.
> Run this on the machine that has access to the local APIs at `127.0.0.1:18081`.

### Run Directly

```bash
source venv/bin/activate
python3 publisher.py
```

Expected console output:
```
AGRI -> sent
WATER -> sent
AGRI -> sent
WATER -> sent
...
```

### Run as a Background Service (systemd)

Create a service file:

```bash
sudo nano /etc/systemd/system/mqtt-publisher.service
```

Paste the following (update paths as needed):

```ini
[Unit]
Description=MQTT Publisher — HTTP API Poller
After=network.target

[Service]
User=your_username
WorkingDirectory=/path/to/project
ExecStart=/path/to/project/venv/bin/python3 publisher.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl start mqtt-publisher
sudo systemctl enable mqtt-publisher

# Check logs
sudo journalctl -u mqtt-publisher -f
```

---

## 4. Deploy `server.py` (Flask REST API Server)

> This server **subscribes to the MQTT broker** and **exposes the data via HTTP REST endpoints**.
> Run this on the machine where you want to serve the REST API.

### Run Directly

```bash
source venv/bin/activate
python3 server.py
```

Expected console output:
```
Connected to MQTT
 * Running on http://127.0.0.1:5000
agri/state {...}
water/state {...}
```

### Test the Endpoints

```bash
# In a new terminal
curl http://127.0.0.1:5000/agri
curl http://127.0.0.1:5000/water
```

### Run as a Background Service (systemd)

```bash
sudo nano /etc/systemd/system/mqtt-server.service
```

```ini
[Unit]
Description=MQTT Flask REST API Server
After=network.target

[Service]
User=your_username
WorkingDirectory=/path/to/project
ExecStart=/path/to/project/venv/bin/python3 server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl start mqtt-server
sudo systemctl enable mqtt-server

# Check logs
sudo journalctl -u mqtt-server -f
```

---

## 5. Quick Start (Both Servers, One Machine for Testing)

```bash
# Terminal 1 — Start Flask REST API server
source venv/bin/activate
python3 server.py

# Terminal 2 — Start MQTT publisher
source venv/bin/activate
python3 publisher.py
```

---

## 6. Configuration Reference

### `publisher.py`

| Variable | Default | Description |
|---|---|---|
| `AGRI_URL` | `http://127.0.0.1:18081/state` | Agricultural API endpoint |
| `WATER_URL` | `http://127.0.0.1:18081/water` | Water system API endpoint |
| `MQTT_HOST` | `<YOUR_VPS_IP>` | VPS MQTT broker IP address |
| `TOPIC_AGRI` | `agri/state` | MQTT topic for agri data |
| `TOPIC_WATER` | `water/state` | MQTT topic for water data |
| `auth_agri` | `("unity", "secret123")` | Basic auth for agri API |
| `auth_water` | `("water", "secret123")` | Basic auth for water API |
| `time.sleep(0)` | `0` | Polling interval in seconds |

### `server.py`

| Variable | Default | Description |
|---|---|---|
| `BROKER` | `localhost` | MQTT broker host to subscribe to |
| Flask host | `127.0.0.1` | Host to bind the REST API |
| Flask port | `5000` | Port to bind the REST API |

---

## 7. Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `Connection refused` on MQTT | Broker not running | Run `sudo systemctl start mosquitto` |
| `Fetch error: timeout` | Local API unreachable | Check if the source API is running on port 18081 |
| `/agri` returns `{}` | No MQTT message received yet | Verify `publisher.py` is running and sending |
| Port 1883 unreachable | Firewall blocking | Open port 1883 on the VPS firewall |
| `ModuleNotFoundError` | Dependencies not installed | Run `pip install -r requirements.txt` |

---

## 8. Security Recommendations (Production)

- Replace `allow_anonymous true` in Mosquitto with password-based auth
- Store API credentials in environment variables instead of hardcoding them
- Use TLS (port 8883) for encrypted MQTT communication
- Bind Flask to `0.0.0.0` only if external access is needed, otherwise keep `127.0.0.1`
- Use `gunicorn` instead of Flask's built-in server for production deployments:

```bash
pip install gunicorn
gunicorn -w 2 -b 127.0.0.1:5000 server:app
```
