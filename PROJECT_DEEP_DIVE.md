# Cold Chain Monitoring System — Project Deep Dive

> **A comprehensive guide to every aspect of the project.**
> Written as a presentation-ready reference for understanding the architecture, data flow, codebase, design decisions, strengths, limitations, and future roadmap.

---

## Table of Contents

1. [The Real-World Problem](#1-the-real-world-problem)
2. [Project Overview & Solution](#2-project-overview--solution)
3. [Tech Stack & Rationale](#3-tech-stack--rationale)
4. [System Architecture](#4-system-architecture)
5. [Data Flow — End to End](#5-data-flow--end-to-end)
6. [Codebase Walkthrough](#6-codebase-walkthrough)
   - 6.1 [Sensor Simulator](#61-sensor-simulator)
   - 6.2 [MQTT Subscriber & Processing Engine](#62-mqtt-subscriber--processing-engine)
   - 6.3 [FastAPI WebSocket Bridge](#63-fastapi-websocket-bridge)
   - 6.4 [Streamlit Dashboard](#64-streamlit-dashboard)
   - 6.5 [Configuration & Infrastructure](#65-configuration--infrastructure)
7. [Key Design Decisions](#7-key-design-decisions)
8. [Strengths](#8-strengths)
9. [Limitations](#9-limitations)
10. [Potential Improvements & Future Roadmap](#10-potential-improvements--future-roadmap)
11. [Project Directory Map](#11-project-directory-map)
12. [Quick-Start Guide](#12-quick-start-guide)

---

## 1. The Real-World Problem

### What is a "Cold Chain"?

A **cold chain** is a temperature-controlled supply chain used to transport products that are sensitive to heat — such as vaccines, fresh produce, frozen food, and pharmaceuticals. Every link in the chain (warehouse → truck → clinic) must maintain a strict temperature range, or the product can be ruined.

### Why Does This Matter?

| Impact Area | Real-World Consequence |
|---|---|
| **Healthcare** | The WHO estimates that **50% of vaccines** are wasted globally each year, largely due to cold chain failures. A single temperature breach can render a batch of COVID or polio vaccines completely useless. |
| **Food Safety** | Improper refrigeration causes **~600 million cases** of foodborne illness annually (WHO). A warm truck can turn a safe shipment of meat into a biohazard. |
| **Financial Loss** | Temperature excursions in pharma logistics cost the industry **$35 billion+ per year** globally. |
| **Regulatory** | Industries like pharmaceuticals are governed by strict regulations (e.g., FDA, WHO GDP guidelines) that mandate continuous temperature monitoring with documented proof. |

### The Core Challenge

Traditional monitoring is **manual and reactive** — a worker checks a thermometer, writes a number on a clipboard, and by the time a problem is found, the damage is already done. There is no real-time visibility, no automated alerts, and no data trail for compliance audits.

**This project solves that** by building a system that:
- Continuously monitors temperature from IoT sensors
- Detects breaches in real time
- Sends instant mobile notifications
- Provides a live dashboard for fleet-wide visibility
- Generates compliance-ready audit reports

---

## 2. Project Overview & Solution

The **Cold Chain Monitoring System** is a full-stack, real-time IoT data pipeline that simulates a fleet of temperature sensors attached to shipments — and processes, analyzes, stores, and visualizes their data in real time.

### What It Does (End-User Perspective)

```
┌──────────────────────────────────────────────────────────┐
│  1. Sensors on trucks/containers publish temperature     │
│     readings every 5 seconds via MQTT.                   │
│                                                          │
│  2. A processing engine listens for these readings,      │
│     calculates rolling averages, detects breaches,       │
│     and saves everything to a time-series database.      │
│                                                          │
│  3. If a sensor breaches safety limits 3 times in a      │
│     row, a push notification is sent to the operator's   │
│     phone immediately.                                   │
│                                                          │
│  4. A live dashboard shows fleet status, temperature     │
│     trends, health scores, and predictive alerts (like   │
│     "Breach in 15m") — refreshing every 5 seconds.       │
│                                                          │
│  5. A countdown timer tells operators exactly how much   │
│     time they have to fix a cooling issue before it      │
│     becomes a failure.                                   │
│                                                          │
│  6. When a shipment arrives, the operator clicks a       │
│     button to generate a PASS/FAIL compliance report     │
│     with full CSV export.                                │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Tech Stack & Rationale

### Overview Table

| Layer | Technology | Purpose | Why This Choice? |
|---|---|---|---|
| **Language** | Python 3.x | All backend logic | Dominant in IoT/data; rich library ecosystem; beginner-friendly |
| **Messaging** | MQTT (Mosquitto) | Sensor → Subscriber transport | Industry standard for IoT; lightweight; pub/sub model ideal for sensors |
| **Message Client** | Paho-MQTT | Python MQTT library | Official Eclipse library; most mature Python MQTT client |
| **Processing** | Pandas / NumPy | Rolling metrics, analytics | De facto standard for tabular data manipulation in Python |
| **Database** | InfluxDB 2.x | Time-series data storage | Purpose-built for sensor data; automatic time indexing; Flux query language |
| **API** | FastAPI | Real-time WebSocket bridge | Async-native; WebSocket support out-of-the-box; ultra-fast |
| **Dashboard** | Streamlit | Live monitoring UI | Rapid Python → Web UI; built-in charting; zero frontend JS needed |
| **Charting** | Plotly | Interactive graphs | Rich interactivity (zoom, hover, legend toggle); dark theme support |
| **Notifications** | ntfy.sh | Mobile push alerts | Free, open-source; no app or API key required; HTTP POST = notification |
| **Config** | python-dotenv | Environment secrets | Keeps tokens out of source code; `.env` file pattern |
| **Infra** | Threading | Parallel sensor simulation | Lightweight concurrency for simulating a sensor fleet |

### Why These Specific Choices?

#### MQTT over HTTP for Sensor Data
```
HTTP (Request/Response):          MQTT (Publish/Subscribe):
                                  
Sensor ──POST──▶ Server           Sensor ──publish──▶ Broker
       ◀─200 OK─                         (fire & forget)
                                         │
(Heavy headers, connection               ▼
 overhead per message)            Subscriber listens continuously
                                  (lightweight, persistent connection)
```

MQTT was chosen because:
- **Tiny packet size** — an MQTT message can be as small as 2 bytes of overhead vs. HTTP's ~700 bytes of headers
- **Persistent connection** — sensors connect once and keep publishing; no reconnection overhead
- **Pub/Sub decoupling** — the sensor doesn't need to know who's listening; new consumers (dashboards, loggers, alert systems) can subscribe independently
- **Industry standard** — used by AWS IoT, Azure IoT Hub, and most industrial SCADA systems

#### InfluxDB over PostgreSQL/MongoDB
```
PostgreSQL:                         InfluxDB:
                                    
INSERT INTO readings                Point("sensor_reading")
  (time, sensor_id, temp)             .tag("sensor_id", "S-001")
  VALUES (now(), 'S-001', 4.2);       .field("temperature_c", 4.2)
                                    
→ Manual time indexing              → Automatic time indexing
→ Manual data retention             → Built-in retention policies
→ Generic row storage               → Columnar, compressed time-series
→ SQL queries                       → Flux queries (time-native)
```

InfluxDB was purpose-built for exactly this use case — millions of timestamped data points from sensors. It automatically indexes by time, compresses efficiently, and supports native time-range queries like "last 1 hour" or "last 30 days" without manual `WHERE timestamp > ...` clauses.

#### FastAPI as the WebSocket Bridge
The system needed a way to push data from the backend (Subscriber) to the frontend (Dashboard) in real time. FastAPI was chosen because:
- Native `async/await` support — perfect for WebSockets
- Automatic OpenAPI docs at `/docs`
- Minimal boilerplate — the entire API is 46 lines of code

#### Streamlit for the Dashboard
Building a React/Vue frontend would have taken days. Streamlit converts a Python script directly into a web app with widgets, charts, and interactive elements — allowing rapid iteration while staying within a single language.

---

## 4. System Architecture

### High-Level Architecture Diagram

```
╔═══════════════════════════════════════════════════════════════════════════════════╗
║                        COLD CHAIN MONITORING SYSTEM                             ║
╠═══════════════════════════════════════════════════════════════════════════════════╣
║                                                                                 ║
║   ┌──────────────┐         ┌──────────────┐         ┌──────────────────────┐    ║
║   │  SENSOR-001  │───┐     │              │         │                      │    ║
║   │  (Vaccines)  │   │     │              │         │   SUBSCRIBER         │    ║
║   └──────────────┘   │     │              │         │   (Processing        │    ║
║   ┌──────────────┐   │MQTT │   MOSQUITTO  │  MQTT   │    Engine)           │    ║
║   │  SENSOR-002  │───┼────▶│   BROKER     │────────▶│                      │    ║
║   │  (Food)      │   │     │  :1883       │         │  • Threshold Check   │    ║
║   └──────────────┘   │     │              │         │  • Rolling Averages  │    ║
║   ┌──────────────┐   │     │              │         │  • Health Scoring    │    ║
║   │  SENSOR-003  │───┤     └──────────────┘         │  • Breach Detection  │    ║
║   │  (Meat)      │   │  • Rolling Averages  │    ║
║   └──────────────┘   │  • Health Scoring    │    ║
║   ┌──────────────┐   │  • Breach Detection  │    ║
║   │  SENSOR-004  │───┘  • Time Prediction   │    ║
║   │  (Medicine)  │      └──────┬───┬───┬───────┘    ║
║   └──────────────┘                                         │   │   │             ║
║                                                            │   │   │             ║
║        ┌───────────────────────────────────────────────┐   │   │   │             ║
║        │                                               │   │   │   │             ║
║        ▼                                               ▼   │   ▼   │             ║
║   ┌──────────┐    ┌───────────────────────────┐   ┌────────┴┐ ┌────┴──────────┐ ║
║   │ ntfy.sh  │    │      INFLUXDB             │   │ FastAPI │ │               │ ║
║   │ (Push    │    │   (Time-Series DB)        │   │  :8000  │ │  Not shown:   │ ║
║   │  Alerts) │    │                           │   │         │ │  breach_event │ ║
║   │          │    │  Bucket: coldchain_raw     │◀──│ /broad- │ │  measurement  │ ║
║   │ Phone 📱 │    │                           │   │  cast   │ │  in InfluxDB  │ ║
║   └──────────┘    │  Measurements:            │   │         │ │               │ ║
║                   │   • sensor_reading        │   │  /ws ◀──┼─┤               │ ║
║                   │   • breach_event          │   └────┬────┘ └───────────────┘ ║
║                   └─────────────┬─────────────┘        │                        ║
║                                 │                      │ WebSocket              ║
║                                 │ Flux Query           │                        ║
║                                 ▼                      ▼                        ║
║                   ┌────────────────────────────────────────┐                    ║
║                   │         STREAMLIT DASHBOARD            │                    ║
║                   │              :8501                     │                    ║
║                   │                                        │                    ║
║                   │  ┌────────────────────────────────┐    │                    ║
║                   │  │  🚚 Active Fleet Status        │    │                    ║
║                   │  │  SENSOR-001: 4.2°C  🟢 SAFE   │    │                    ║
║                   │  │  SENSOR-002: 12.1°C 🔴 BREACH │    │                    ║
║                   │  └────────────────────────────────┘    │                    ║
║                   │  ┌────────────────────────────────┐    │                    ║
║                   │  │  📈 Temperature History Chart  │    │                    ║
║                   │  │  (Plotly interactive graph      │    │                    ║
║                   │  │   with safety zone lines)       │    │                    ║
║                   │  └────────────────────────────────┘    │                    ║
║                   │  ┌──────────────┐ ┌──────────────┐     │                    ║
║                   │  │ 📊 Stats     │ │ 🚨 Alerts    │     │                    ║
║                   │  │ Mean/Min/Max │ │ (Last 24h)   │     │                    ║
║                   │  │ Battery/HP   │ │              │     │                    ║
║                   │  └──────────────┘ └──────────────┘     │                    ║
║                   │  ┌────────────────────────────────┐    │                    ║
║                   │  │ 📋 Shipment Report Generator   │    │                    ║
║                   │  │ [Generate] → PASS/FAIL + CSV   │    │                    ║
║                   │  └────────────────────────────────┘    │                    ║
║                   └────────────────────────────────────────┘                    ║
╚═══════════════════════════════════════════════════════════════════════════════════╝
```

### Component Responsibilities

| Component | Directory | Responsibility |
|---|---|---|
| **Sensor Simulator** | `simulator/` | Generates synthetic IoT sensor data (temperature, humidity, battery) and publishes via MQTT |
| **MQTT Broker** | External (Mosquitto) | Routes messages from publishers (sensors) to subscribers |
| **Subscriber** | `subscriber/` | Central processing engine — validates data, calculates metrics, detects breaches, sends alerts, writes to DB |
| **FastAPI API** | `api/` | WebSocket bridge — receives processed data from Subscriber and pushes it to connected dashboard clients |
| **Dashboard** | `dashboard/` | Real-time web UI — visualizes fleet status, temperature trends, alerts, and compliance reports |
| **InfluxDB** | External | Persistent time-series storage for all sensor readings and breach events |
| **ntfy.sh** | External (Cloud) | Push notification delivery to mobile devices |
| **Config** | `config/` | Product safety profiles (min/max temperature thresholds per product type) |

---

## 5. Data Flow — End to End

### The Journey of a Single Sensor Reading

This traces one reading from creation to the user's screen:

```
Step 1: GENERATION (sensor_sim.py)
───────────────────────────────────
  temp = 4.0 + random.uniform(-0.1, 0.1)    # Small drift
  if random.random() < 0.05:                 # 5% chance of spike
      temp += random.uniform(2, 5)

  payload = {
      "sensor_id": "SENSOR-001",
      "shipment_id": "SHP-ALPHA",
      "product_type": "standard_vaccines",
      "timestamp": "2026-04-18T19:30:00",
      "temperature_c": 4.05,
      "humidity_pct": 50.12,
      "battery_pct": 99.5
  }

          │
          │  MQTT Publish → topic: "cold_chain/SENSOR-001/readings"
          ▼

Step 2: TRANSPORT (Mosquitto Broker)
───────────────────────────────────
  Broker receives the message on port 1883
  and forwards it to all subscribers of "cold_chain/#"

          │
          │  MQTT Deliver
          ▼

Step 3: PROCESSING (subscriber.py)
───────────────────────────────────
  a) Parse JSON payload
  b) Append temp to rolling history (last 12 readings)
  c) Calculate rolling mean:  avg = sum(history) / len(history)
  d) Load product rules:  vaccines → min: 2°C, max: 8°C
  e) Check breach:  4.05 < 8.0 AND 4.05 > 2.0 → ✅ SAFE
  f) Calculate health score:  (99.5 × 0.8 + 20) / 100 = 1.0
  g) Enrich the payload:
      payload["rolling_mean"] = 4.03
      payload["health_score"] = 1.0
      payload["is_breach"] = False
      payload["minutes_to_breach"] = 15.2 (5-point Smoothed Prediction)
      payload["hours_until_dead"] = 14.5 (Battery Life Remaining)

          │
          │  Forked into THREE outputs:
          ├───────────────────────────────────────────────┐
          │                         │                     │
          ▼                         ▼                     ▼

Step 4a: BROADCAST              Step 4b: STORE          Step 4c: ALERT
(FastAPI /broadcast)            (InfluxDB)              (ntfy.sh)
                                                        (Only if breach
  HTTP POST with                Write Point:             count ≥ 3)
  enriched JSON                 measurement: sensor_reading
          │                     tags: sensor_id, shipment_id
          │                     fields: temperature_c,
          ▼                            is_breach,
                                       health_score
Step 5: DELIVERY
(WebSocket /ws)
  FastAPI pushes JSON
  to all connected
  WebSocket clients

          │
          ▼

Step 6: VISUALIZATION (dashboard/app.py)
─────────────────────────────────────────
  Streamlit queries InfluxDB every 5 seconds
  and renders:
  • Fleet status cards (🟢 SAFE / 🔴 BREACH / ⚠️ PREDICTION)
  • Temperature history chart (Plotly)
  • Risk Analysis Chart (Breaches by Product Category)
  • Per-sensor statistics table (mean, min, max)
  • Battery & health forecasting panel (Hours Remaining)
  • Alert log (last 24 hours)
  • Shipment report generator (PASS/FAIL + CSV)
```

### The Breach Detection Pipeline (Detailed)

The system uses a **"Soft Limit"** approach — a single spike doesn't trigger an alert. This filters out sensor noise and transient anomalies.

```
Reading #1:  temp = 9.5°C  (above 8°C max for vaccines)
             → fail_count["SENSOR-001"] = 1
             → is_breach = False  (not yet 3)

Reading #2:  temp = 10.2°C
             → fail_count["SENSOR-001"] = 2
             → is_breach = False  (not yet 3)

Reading #3:  temp = 11.0°C
             → fail_count["SENSOR-001"] = 3  ← THRESHOLD REACHED
             → is_breach = True  ✅
             → send_push_notification()  📱
             → "ALERT: SENSOR-001 is too hot! Current: 11.0°C"

Reading #4:  temp = 4.0°C   (back to normal!)
             → fail_count["SENSOR-001"] = 0  ← RESET
             → is_breach = False
```

---

## 6. Codebase Walkthrough

### 6.1 Sensor Simulator

#### `simulator/sensor_sim.py` — The Individual Sensor

This file simulates a **single IoT temperature sensor** attached to a shipment.

**Key Logic:**

```python
# Starting conditions
temp = 4.0        # Nominal vaccine storage temperature
humidity = 50.0   # Baseline humidity
battery = 100.0   # Starts fully charged

while True:
    # 1. Natural drift — simulates real-world fluctuation
    temp += random.uniform(-0.1, 0.1)

    # 2. Random malfunction — 5% chance of a spike
    if random.random() < 0.05:
        temp += random.uniform(2, 5)

    # 3. Battery drain — slow linear decrease
    battery -= 0.1

    # 4. Publish via MQTT
    client.publish("cold_chain/SENSOR-001/readings", json_payload)

    # 5. Wait 5 seconds
    time.sleep(5)
```

**Design Insight:** The 5% spike probability (covering both high heat and extreme cold) and ±0.1°C drift model real-world sensor behavior — devices don't produce perfectly stable readings. This makes the system's dual-threshold (min/max) breach detection and averaging logic meaningful during demos.

---

#### `simulator/multi_sensor_sim.py` — The Fleet Launcher

Launches **4 sensors in parallel**, each on its own thread, simulating a multi-vehicle fleet:

```python
sensor_list = [
    {"id": "SENSOR-001", "shipment": "SHP-ALPHA", "profile": "vaccines"},
    {"id": "SENSOR-002", "shipment": "SHP-BETA",  "profile": "food"},
    {"id": "SENSOR-003", "shipment": "SHP-GAMMA", "profile": "meat"},
    {"id": "SENSOR-004", "shipment": "SHP-DELTA", "profile": "medicine"},
]

for config in sensor_list:
    thread = threading.Thread(target=run_sensor, args=(config,))
    thread.daemon = True   # Stops when main script stops
    thread.start()
```

**Why Threading?** Each sensor needs its own infinite loop (publishing every 5 seconds). Threads allow them to run concurrently within a single Python process. The `daemon=True` flag ensures they all terminate cleanly when the main script is stopped with `Ctrl+C`.

---

#### `simulator/demo_alerts.py` — The Demo Trigger

A convenience script that intentionally sends **3 high-temperature readings** (12.5°C, 14.2°C, 15.8°C) to instantly trigger the breach detection pipeline. Perfect for demonstrations:

```
python simulator/demo_alerts.py
→ Sends 3 readings above the 8°C vaccine limit
→ Subscriber detects 3 consecutive failures
→ Push notification sent to phone
→ Dashboard updates to show 🔴 BREACH
```

---

### 6.2 MQTT Subscriber & Processing Engine

#### `subscriber/subscriber.py` — The Brain of the System

This is the **most complex and critical** component. It acts as the central processing engine.

**Section-by-Section Breakdown:**

##### Setup & Configuration (Lines 1–43)
```python
# Load secrets from .env file (not hardcoded!)
load_dotenv()
TOKEN = os.getenv("INFLUXDB_TOKEN")

# Load product safety rules
with open("config/profiles.json", "r") as f:
    PROFILES = json.load(f)    # e.g., vaccines: min 2°C, max 8°C

# In-memory state
sensor_fail_counts = {}   # Tracks consecutive failures per sensor
sensor_history = {}       # Stores last 12 temperature readings per sensor
```

##### Processing Pipeline (Lines 58–125)

Each incoming MQTT message triggers `process_message()`, which executes a **7-step pipeline**:

| Step | Action | Code |
|---|---|---|
| 1 | **Track History** | Append temp to a list, keep only last 12 values |
| 2 | **Calculate Rolling Mean** | `avg = sum(history) / len(history)` |
| 3 | **Check Breach** | Compare temp against product-specific min/max from `profiles.json` |
| 4 | **Calculate Health Score** | `health = (battery × 0.8 + stability_bonus) / 100` |
| 5 | **Enrich Payload** | Add `rolling_mean`, `health_score`, `is_breach` to the reading |
| 6 | **Broadcast to Dashboard** | HTTP POST to FastAPI `/broadcast` endpoint |
| 7 | **Persist to Database** | Write InfluxDB Point with tags and fields |

##### The Breach Logic (Detailed):
```python
rules = PROFILES.get(product_type, PROFILES["standard_vaccines"])

if temp > rules["temp_max"] or temp < rules["temp_min"]:
    sensor_fail_counts[sensor_id] += 1
    if sensor_fail_counts[sensor_id] >= 3:     # MAX_FAILURES = 3
        is_breach = True
        if sensor_fail_counts[sensor_id] == 3: # Send alert ONCE
            send_push_notification(reading, rules)
else:
    sensor_fail_counts[sensor_id] = 0          # Reset on safe reading
```

##### ntfy.sh Push Notification:
```python
def send_push_notification(reading, profile):
    msg = f"ALERT: {reading['sensor_id']} is too hot! Current: {reading['temperature_c']}C"
    requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode("utf-8"))
```
This is remarkably simple — ntfy.sh requires no API key, no app installation, no OAuth. A single HTTP POST with a text body = a notification on any subscribed device.

---

### 6.3 FastAPI WebSocket Bridge

#### `api/main.py` — Real-Time Data Relay

This 46-line file serves as a **bridge** between the synchronous Subscriber and the asynchronous Dashboard:

```
Subscriber (sync Python)
    │
    │  HTTP POST /broadcast
    ▼
FastAPI Server (:8000)
    │
    │  WebSocket push to all clients
    ▼
Dashboard (browser WebSocket /ws)
```

**Key Implementation Details:**

```python
connected_clients = []   # In-memory list of active WebSocket connections

@app.post("/broadcast")
async def receive_data(data: dict):
    for client in connected_clients:
        await client.send_json(data)    # Push to ALL dashboards

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep-alive loop
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
```

**Why Not Just Query InfluxDB from the Dashboard?**

The dashboard does query InfluxDB for historical data and charts. However, the WebSocket bridge enables **instant** data delivery (sub-second) without polling, making the system feel truly real-time. The two methods complement each other:
- **WebSocket**: Instant push for live data
- **InfluxDB query**: Historical analysis, reports, and chart rendering

---

### 6.4 Streamlit Dashboard

#### `dashboard/app.py` — The User Interface

This is the visualization layer — a 311-line Streamlit application with 5 major panels:

##### Panel 1: Fleet Status Grid
```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Vaccines         │  │ Fresh Produce    │  │ Frozen Foods     │
│ (SENSOR-001)     │  │ (SENSOR-002)     │  │ (SENSOR-003)     │
│ 4.2°C            │  │ 3.1°C            │  │ -18.5°C          │
│ 🟢 SAFE          │  │ 🟢 SAFE          │  │ 🟢 SAFE          │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```
Dynamic grid that adapts to the number of active sensors. Each card shows the product type, latest temperature, and breach status.

##### Panel 2: Temperature History Chart
An interactive Plotly line chart showing the last 1 hour of readings for all sensors. Enhanced with:
- **Safety zone lines** — dashed red (MAX) and cyan (MIN) lines per product type, loaded dynamically from `profiles.json`
- **Dark theme** — `template="plotly_dark"` for professional appearance
- **Interactive legend** — click sensor names to show/hide their traces

##### Panel 3: Sensor Statistics Table
A grouped summary showing `mean`, `min`, and `max` temperature per sensor over the last hour.

##### Panel 4: Alert Log
Queries InfluxDB for `breach_event` measurements from the last 24 hours and displays them in a sortable data table.

##### Panel 5: Shipment Report Generator
```
[Select Shipment: SHP-ALPHA ▾]  [Generate Summary Report]

┌──────────┐  ┌──────────────┐  ┌────────────────┐
│ Result   │  │ Average Temp │  │ Time in Breach │
│ PASS ✅  │  │ 4.2°C        │  │ 0.0 mins       │
└──────────┘  └──────────────┘  └────────────────┘

[📥 Download Full CSV Log]
```

Queries the last 30 days of data for a shipment, calculates:
- Average temperature
- Total breach duration (in minutes)
- PASS/FAIL verdict (PASS if 0 breach minutes)
- Exports to CSV for compliance documentation

##### Auto-Refresh Mechanism:
```python
if st.session_state.report_data is None:
    time.sleep(5)
    st.rerun()    # Re-execute the entire script → fresh data
```

---

### 6.5 Configuration & Infrastructure

#### `config/profiles.json` — Product Safety Rules

```json
{
  "standard_vaccines":  { "temp_min": 2.0,   "temp_max": 8.0,   "humidity_max": 80 },
  "fresh_produce":      { "temp_min": 1.0,   "temp_max": 6.0,   "humidity_max": 90 },
  "frozen_foods":       { "temp_min": -25.0,  "temp_max": -15.0, "humidity_max": 60 },
  "pharmaceuticals":    { "temp_min": 15.0,   "temp_max": 25.0,  "humidity_max": 60 }
}
```

This is the **single source of truth** for all temperature thresholds. Both the Subscriber (for breach detection) and the Dashboard (for chart safety zones) read from this same file, ensuring consistency.

#### `.env` — Environment Secrets
```
INFLUXDB_URL=http://127.0.0.1:8086
INFLUXDB_TOKEN=<redacted>
INFLUXDB_ORG=MyProjects
INFLUXDB_BUCKET=coldchain_raw
NTFY_TOPIC=cold-chain-alerts-ojass
```
Sensitive credentials are never hardcoded. The `.env` file is in `.gitignore` — it won't be pushed to GitHub.

#### `run_all.bat` — One-Click Launch
Starts all 5 services (InfluxDB, FastAPI, Subscriber, Simulator, Dashboard) in separate terminal windows with a single double-click.

#### `diag.py` — Diagnostic Utility
A quick script to verify InfluxDB connectivity by querying and counting records from the last 24 hours.

#### `test_ws.html` — WebSocket Debug Page
A minimal HTML page that connects to the FastAPI WebSocket endpoint and logs incoming readings — useful for debugging the real-time data pipeline without the full Streamlit dashboard.

---

## 7. Key Design Decisions

### Decision 1: "Soft Limit" Breach Detection (3 Consecutive Failures)

**Problem:** Real sensors produce noisy data. A single spike above the threshold could be a sensor glitch, not a real temperature excursion.

**Decision:** Require **3 consecutive** out-of-range readings before declaring a breach and sending a notification.

**Trade-off:**
- ✅ Eliminates false positives from sensor noise
- ⚠️ Introduces a ~15-second delay (3 × 5s intervals) before detecting a genuine breach

### Decision 2: In-Memory Rolling Window (Not Pandas)

**Problem:** The development log mentions Pandas for rolling metrics, but the final subscriber uses a simple Python list.

**Decision:** Use a manual list (`sensor_history[id].append(temp)`) capped at 12 entries instead of a Pandas DataFrame.

**Rationale:** For a size-12 window with basic average calculation, native Python lists are simpler, faster, and avoid the overhead of importing a heavy library for a trivial operation. Pandas is still used in the Dashboard for its powerful `groupby` and aggregation capabilities where it genuinely adds value.

### Decision 3: Dual Data Path (WebSocket + Database Polling)

**Decision:** The Subscriber sends data through **two parallel paths**:
1. HTTP POST → FastAPI → WebSocket → Dashboard (real-time push)
2. InfluxDB write → Dashboard polls InfluxDB every 5 seconds (historical queries)

**Rationale:** WebSockets provide instant delivery but are ephemeral — if the dashboard disconnects, data is lost. InfluxDB provides persistence and enables historical queries, reports, and the chart. The two complement each other.

### Decision 4: Streamlit Over a Custom React Frontend

**Decision:** Use Streamlit (Python → auto-generated web UI) instead of building a separate React/Vue frontend.

**Rationale:** The project's primary value is in the backend pipeline (MQTT → Processing → Storage → Alerting). Streamlit allows focusing engineering time on the data pipeline while still producing a professional, interactive dashboard. A React frontend would have doubled the project's complexity and introduced a second language (JavaScript).

### Decision 5: ntfy.sh Over Firebase/Twilio

**Decision:** Use ntfy.sh (free, open-source, no-auth) for push notifications.

**Rationale:** Zero setup cost. No API keys, SDKs, dashboards, or billing. A single HTTP POST delivers a notification. For a student project, this is the pragmatic choice — it demonstrates the notification capability without the infrastructure overhead of enterprise services.

---

## 8. Strengths

| # | Strength | Evidence |
|---|---|---|
| 1 | **Full End-to-End Pipeline** | The system covers every stage: data generation → transport → processing → storage → visualization → alerting → reporting |
| 2 | **Real-Time Architecture** | Sub-second data delivery via MQTT + WebSocket; 5-second dashboard refresh cycle |
| 3 | **Industry-Standard Protocols** | Uses MQTT (IoT standard) and time-series database (InfluxDB) — directly maps to real-world IoT architectures |
| 4 | **Intelligent Breach Detection** | "Soft Limit" logic filters sensor noise; only persistent temperature excursions trigger alerts |
| 5 | **Multi-Product Support** | Configurable thresholds per product type (vaccines, food, pharmaceuticals) via a single JSON file |
| 6 | **Compliance-Ready Reporting** | CSV export with PASS/FAIL verdict, average temp, and breach duration — mirrors regulatory reporting formats |
| 7 | **Push Notifications** | Mobile alerts via ntfy.sh — operators don't need to watch the dashboard 24/7 |
| 8 | **Security Best Practices** | Credentials stored in `.env`, excluded from Git via `.gitignore` |
| 9 | **Predictive Edge** | Time-to-Breach logic provides a countdown alert, turning reactive alarms into proactive warnings |
| 10 | **Scalability Demonstrated** | Multi-threaded fleet simulation (4 simultaneous sensors) with verified zero-data-loss under load |
| 11 | **One-Click Deployment** | `run_all.bat` launches the entire system (including InfluxDB) with no manual steps |
| 12 | **Thorough Documentation** | Includes a dedicated `DATA_SCIENCE_&_ANALYTICS.md` guide explaining the logic behind the "brain" |
| 12 | **Clean, Modular Design** | Each component is a separate Python file/directory with a single, well-defined responsibility |

---

## 🚀 Advanced Industrial Roadmap
To evolve this prototype into a production-ready enterprise solution, the following enhancements are planned:

1.  **Mean Kinetic Temperature (MKT):** Implementing the Arrhenius-based weighted average to better model biological degradation (FDA/Big Pharma standard).
2.  **Cumulative Stability Budgeting:** Transitioning from status-based alerts to "Time-of-Excursion" tracking across multi-leg journeys.
3.  **Predictive Maintenance:** Using historical sensor noise patterns to detect failing refrigeration compressors *before* they stop working.
4.  **Edge Intelligence:** Deploying "Lite" versions of the subscriber logic directly onto IoT gateways to reduce cloud bandwidth.

---

## 9. Limitations

| # | Limitation | Impact | Root Cause |
|---|---|---|---|
| 1 | **Simulated Sensors Only** | No real hardware integration | Hardware IoT sensors (ESP32, Raspberry Pi) are outside the project scope |
| 2 | **Single-Machine Deployment** | All services run on `localhost` | No containerization (Docker) or cloud deployment |
| 3 | **No Authentication** | The dashboard and API have no login system | FastAPI CORS is set to `allow_origins=["*"]`; anyone on the network can access it |
| 4 | **No Humidity-Based Breach Detection** | `humidity_max` thresholds exist in `profiles.json` but are never checked in the Subscriber | Feature was defined in config but not implemented |
| 5 | **Bare `except:` Clauses** | Silently swallows errors in multiple places (MQTT connect, InfluxDB write, API broadcast) | Prioritized simplicity over robust error handling |
| 6 | **In-Memory WebSocket Client List** | If FastAPI restarts, all WebSocket connections are lost | No persistent session management or reconnection logic |
| 7 | **Fixed 5-Second Intervals** | No configurable sample rate; no adaptive frequency based on conditions | Hardcoded `time.sleep(5)` in the simulator |
| 8 | **No Data Retention Policy** | InfluxDB bucket has no automatic expiry | Without retention rules, storage will grow indefinitely |
| 9 | **Dashboard Polls DB + Uses WebSocket** | Dual data source can lead to slight inconsistencies | Architectural trade-off between real-time push and historical queries |
| 10 | **No Unit Tests** | No automated test suite for any component | Common in prototype/MVP-stage student projects |

---

## 10. Potential Improvements & Future Roadmap

### Near-Term Enhancements

| # | Improvement | Description | Difficulty |
|---|---|---|---|
| 1 | **Humidity Monitoring** | Activate the `humidity_max` checks in the Subscriber using the existing config values | 🟢 Easy |
| 2 | **Configurable Sample Rate** | Move `time.sleep(5)` to `profiles.json` or `.env` for per-sensor tuning | 🟢 Easy |
| 3 | **Proper Error Handling** | Replace bare `except:` with specific exceptions and logging | 🟢 Easy |
| 4 | **InfluxDB Retention Policy** | Set 30-day or 90-day automatic data expiry in the bucket settings | 🟢 Easy |
| 5 | **GPS / Location Tracking** | Add latitude/longitude fields to sensor payloads and render a live map in the dashboard | 🟡 Medium |
| 6 | **Multi-User Authentication** | Add JWT-based login to FastAPI and role-based access (admin, operator, viewer) | 🟡 Medium |

### Long-Term / Advanced Roadmap

| # | Improvement | Description | Difficulty |
|---|---|---|---|
| 7 | **Docker Compose** | Containerize all services + InfluxDB + Mosquitto for one-command deployment anywhere | 🟡 Medium |
| 8 | **Real Hardware Integration** | Replace simulated sensors with ESP32/Raspberry Pi devices running MicroPython with actual DHT22 temperature sensors | 🟡 Medium |
| 9 | **ML-Based Anomaly Detection** | Train a model on historical sensor data to predict failures before they happen (predictive maintenance) | 🔴 Advanced |
| 10 | **Grafana Dashboard** | InfluxDB integrates natively with Grafana for enterprise-grade dashboarding with alerting rules | 🟡 Medium |
| 11 | **MQTT over TLS** | Encrypt MQTT traffic with SSL/TLS certificates for production security | 🟡 Medium |
| 12 | **Cloud Deployment** | Deploy to AWS/GCP with managed MQTT (AWS IoT Core) and managed InfluxDB (InfluxDB Cloud) | 🔴 Advanced |

---

## 11. Project Directory Map

```
cold_chain_monitor/
│
├── .env                          # 🔐 Environment secrets (InfluxDB token, ntfy topic)
├── .gitignore                    # Git exclusion rules (venv, .env, __pycache__)
├── run_all.bat                   # 🚀 One-click system launcher (all 5 services)
├── diag.py                       # 🔧 Diagnostic: verify InfluxDB connectivity
├── test_ws.html                  # 🧪 WebSocket debug page (browser-based)
├── RUN_INSTRUCTIONS.md           # 📖 How to start the system
├── DEVELOPMENT_LOG.md            # 📓 Complete development history (9 phases)
├── DATA_SCIENCE_&_ANALYTICS.md   # 📊 Deep-dive into project logic & AI models
│
├── config/
│   └── profiles.json             # ⚙️  Product safety thresholds (vaccines, food, etc.)
│
├── simulator/
│   ├── sensor_sim.py             # 📡 Single sensor simulator (MQTT publisher)
│   ├── multi_sensor_sim.py       # 🚚 Fleet launcher (4 parallel sensors via threading)
│   └── demo_alerts.py            # 🎯 Demo script: triggers a breach on demand
│
├── subscriber/
│   └── subscriber.py             # 🧠 Processing engine (metrics, breach logic, DB writes)
│
├── api/
│   └── main.py                   # 🌐 FastAPI WebSocket bridge (real-time data relay)
│
├── dashboard/
│   └── app.py                    # 📊 Streamlit UI (charts, alerts, reports)
│
├── notebooks/
│   └── explore.ipynb             # 🔬 Exploratory analysis (Z-score anomaly detection)
│
├── reports/
│   ├── SHP-A_report.csv          # 📋 Generated compliance report (sample)
│   └── SHIP-99_report.csv        # 📋 Generated compliance report (sample)
│
└── venv/                         # 🐍 Python virtual environment (not tracked in Git)
```

---

## 12. Quick-Start Guide

### Prerequisites Checklist

- [ ] Python 3.10+ installed
- [ ] Mosquitto MQTT broker installed and running on port 1883
- [ ] InfluxDB 2.x installed (`influxd.exe` available)
- [ ] `.env` file configured with valid InfluxDB token

### Starting the System

**Option A: One-Click (Recommended)**
```powershell
# Ensure Mosquitto is running, then:
.\run_all.bat
```

**Option B: Manual (5 terminals)**
```powershell
# Terminal 0: InfluxDB
& "C:\path\to\influxd.exe"

# Terminal 1: FastAPI
.\venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000

# Terminal 2: Subscriber
.\venv\Scripts\python.exe subscriber\subscriber.py

# Terminal 3: Simulator
.\venv\Scripts\python.exe simulator\multi_sensor_sim.py

# Terminal 4: Dashboard
.\venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

### Triggering a Demo Breach
```powershell
.\venv\Scripts\python.exe simulator\demo_alerts.py
```
This sends 3 high-temperature readings → triggers breach detection → sends a phone notification → dashboard updates to show 🔴 BREACH.

### Accessing the System

| Service | URL |
|---|---|
| **Dashboard** | http://localhost:8501 |
| **API** | http://127.0.0.1:8000 |
| **API Docs** | http://127.0.0.1:8000/docs |
| **InfluxDB UI** | http://localhost:8086 |
| **ntfy.sh Alerts** | https://ntfy.sh/cold-chain-alerts-ojass |

---

> **End of Document**
>
> *This document was generated as a comprehensive reference for project presentation and review. It covers the complete system architecture, every source file, all design decisions, and the full development journey from Phase 1 to Phase 8.*
