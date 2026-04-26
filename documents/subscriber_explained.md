# Cold Chain Monitor - Subscriber Service

## Overview

`subscriber.py` is the **brain** of the cold chain monitoring system. It's a Python service that subscribes to MQTT sensor data, validates readings against product-specific thresholds, predicts future failures, stores data in InfluxDB, and sends alert notifications.

## Purpose

This subscriber acts as the central processing hub that:

1. **Collects** real-time sensor data from all devices via MQTT
2. **Validates** each reading against configurable product profiles
3. **Predicts** imminent failures before they become critical
4. **Persists** historical data to InfluxDB time-series database
5. **Notifies** personnel via push notifications when alerts trigger
6. **Feeds** processed data to the web dashboard

## Architecture & Data Flow

```
┌─────────────────┐
│  Sensor Sim     │  (sensor_sim.py)
│  (MQTT Pub)     │
└────────┬────────┘
         │ MQTT Messages
         │ cold_chain/TEMP-001/readings
         ▼
┌─────────────────────────────────────────────────────────┐
│                    MQTT Broker                          │
│               (localhost:1883)                          │
└────────┬───────────────────────────────────────┬────────┘
         │                                       │
         │ Subscribes to:                        │
         │ cold_chain/#                          │
         ▼                                       │
┌─────────────────────────────────────────────────────┐    │
│         subscriber.py                               │    │
│  ┌─────────────────────────────────────────────────┐ │    │
│  │  1. Receive MQTT message                        │ │    │
│  │  2. Parse JSON payload                          │ │    │
│  │  3. Load product profile from profiles.json     │ │    │
│  │  4. Check for threshold breaches                │ │    │
│  │     - Consecutive failure counting (3 strikes)  │ │    │
│  │  5. Calculate metrics:                          │ │    │
│  │     • Rolling average (last 12 readings)        │ │    │
│  │     • Health score (battery + status)           │ │    │
│  │     • Time-to-breach prediction                  │ │    │
│  │     • Battery life prediction                    │ │    │
│  │  6. Send push notification (if breach)          │ │    │
│  │  7. POST to dashboard API                        │ │    │
│  │  8. Write to InfluxDB                            │ │    │
│  └─────────────────────────────────────────────────┘ │    │
└───────────────┬─────────────────────────────────────┘    │
                │                                          │
                │ HTTP POST                                │
                ▼                                          │
┌──────────────────────────┐                              │
│  Dashboard API           │                              │
│  (http://localhost:8000) │◄─────────────────────────────┘
│  /broadcast endpoint     │
└──────────┬───────────────┘
           │
           │ WebSocket / SSE
           ▼
┌──────────────────────────┐
│  Web Dashboard           │
│  (React/Vue/HTML)        │
│  - Real-time readings    │
│  - Charts & graphs       │
│  - Alert history         │
└──────────────────────────┘
```

## Configuration

### Environment Variables (`.env` file)

```bash
INFLUXDB_URL=http://127.0.0.1:8086
INFLUXDB_TOKEN=your-token-here
INFLUXDB_ORG=your-org
INFLUXDB_BUCKET=cold_chain
NTFY_TOPIC=cold-chain-alerts
```

### Constants (Hardcoded)

```python
BROKER = "127.0.0.1"          # MQTT broker address
TOPIC = "cold_chain/#"        # Subscribe to all sensor topics
API_URL = "http://127.0.0.1:8000/broadcast"  # Dashboard endpoint
MAX_FAILURES = 3              # Consecutive failures before alert
```

## Code Walkthrough

### Section 1: Setup & Configuration (Lines 1-46)

**Imports**:
```python
import json                    # Parse MQTT payloads
import os                      # Read environment variables
import requests                # HTTP calls to dashboard & ntfy
import paho.mqtt.client as mqtt  # MQTT subscription
from datetime import datetime  # Timestamps (not directly used)
from dotenv import load_dotenv # Load .env file
from influxdb_client import InfluxDBClient, Point  # Time-series DB
from influxdb_client.client.write_api import SYNCHRONOUS
```

**Load Product Profiles** (Lines 34-36):
```python
with open("config/profiles.json", "r") as f:
    PROFILES = json.load(f)
```
Loads temperature/humidity thresholds into memory. Example:
```python
PROFILES = {
    "vaccines": {"temp_min": 2.0, "temp_max": 8.0, "humidity_max": 80},
    "fresh_produce": {"temp_min": 1.0, "temp_max": 6.0, "humidity_max": 90},
    ...
}
```

**InfluxDB Connection** (Lines 38-45):
```python
influx = InfluxDBClient(url=INFLUX_URL, token=TOKEN, org=ORG)
writer = influx.write_api(write_options=SYNCHRONOUS)
```
- Uses **synchronous writes** to ensure data is persisted before continuing
- If connection fails, `writer = None` and database writes are skipped (graceful degradation)

### Section 2: Notification Helper (Lines 49-59)

```python
def send_push_notification(reading, profile):
    temp = reading["temperature_c"]
    status = "too hot" if temp > profile["temp_max"] else "too cold"

    msg = f"ALERT: {reading['sensor_id']} is {status}! Current: {temp}C"
    requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode("utf-8"))
```

**How ntfy.sh works**:
- Free push notification service
- Sends to topic `cold-chain-alerts`
- Users subscribe via mobile app or web to receive alerts
- No authentication required for public topics

**Example notification**:
```
ALERT: TEMP-001 is too hot! Current: 12.5C
```

**Why send notifications only on MAX_FAILURES?**
- Prevents alert fatigue from transient spikes (e.g., door opening for 10 seconds)
- Requires 3 consecutive out-of-range readings (≥15 seconds) before alert
- Gives the system time to self-correct

### Section 3: Message Processing (Lines 63-183)

The `process_message()` function is called for each MQTT message.

#### Step 1: Parse Payload (Lines 65-69)

```python
raw_data = message.payload.decode()
reading = json.loads(raw_data)
s_id = reading["sensor_id"]
temp = reading["temperature_c"]
```

**Incoming JSON Example**:
```json
{
  "sensor_id": "TEMP-001",
  "shipment_id": "SHP-2024-ABCD",
  "product_type": "vaccines",
  "timestamp": "2025-04-21T12:00:05.123456",
  "temperature_c": 9.2,
  "humidity_pct": 65.0,
  "battery_pct": 87.5
}
```

#### Step 2: Track Rolling History (Lines 72-78)

```python
if s_id not in sensor_history:
    sensor_history[s_id] = []

sensor_history[s_id].append(temp)

# Keep only the last 12 readings
if len(sensor_history[s_id]) > 12:
    sensor_history[s_id].pop(0)
```

**Why 12 readings?**
- Covers 1 minute of data (12 readings × 5 seconds each)
- Provides enough points for trend analysis
- Smooths out minor fluctuations

**Example history** (for sensor TEMP-001):
```
Reading #1:  4.0°C  → [4.0]
Reading #2:  4.1°C  → [4.0, 4.1]
Reading #3:  4.2°C  → [4.0, 4.1, 4.2]
...
Reading #12: 4.3°C  → [4.0, 4.1, ..., 4.3]  (12 items)
Reading #13: 4.4°C  → pop 4.0, append 4.4 → [4.1, 4.2, ..., 4.4]
```

#### Step 3: Calculate Average (Lines 81-82)

```python
history = sensor_history[s_id]
avg_temp = sum(history) / len(history)
```

**Example** (12 readings):
```
[4.0, 4.1, 4.2, 4.0, 4.1, 4.2, 4.1, 4.0, 4.2, 4.1, 4.0, 4.1]
Sum = 49.1
Average = 49.1 / 12 = 4.09°C
```

#### Step 4: Check for Breaches (Lines 85-101)

```python
p_type = reading.get("product_type", "vaccines")
rules = PROFILES.get(p_type, PROFILES["standard_vaccines"])

is_breach = False

if temp > rules["temp_max"] or temp < rules["temp_min"]:
    current_fails = sensor_fail_counts.get(s_id, 0) + 1
    sensor_fail_counts[s_id] = current_fails

    if current_fails >= MAX_FAILURES:
        is_breach = True
        if current_fails == MAX_FAILURES:
            send_push_notification(reading, rules)
else:
    sensor_fail_counts[s_id] = 0
```

**Example Scenario**:
```
Sensor: TEMP-001 (vaccines, range 2-8°C)

Reading 1: temp = 9.5°C  → fail_count = 1 (no alert)
Reading 2: temp = 9.8°C  → fail_count = 2 (no alert)
Reading 3: temp = 9.3°C  → fail_count = 3 → ALERT! send_push_notification()
Reading 4: temp = 9.6°C  → fail_count = 4 (is_breach = True, no new notification)
Reading 5: temp = 7.5°C  → back in range → fail_count = 0
```

**Why 3 consecutive failures?**
- Filters out momentary glitches (door opened briefly, sensor error)
- Ensures sustained condition before notifying
- Reduces false positives while maintaining responsiveness

#### Step 5: Calculate Health Score (Lines 104-107)

```python
battery = reading.get("battery_pct", 100)
health = (battery * 0.8) + (20 if not is_breach else 0)
health = round(health / 100, 2)
```

**Formula**:
```
Health Score = (battery × 0.8) + (20 if no breach else 0)  [0-100]
Then normalized: ÷ 100 → [0.00, 1.00]
```

**Example**:
- Battery = 85%, no breach → (85 × 0.8) + 20 = 68 + 20 = 88 → 0.88
- Battery = 30%, breach → (30 × 0.8) + 0 = 24 → 0.24

**Interpretation**:
- **0.80-1.00**: Healthy (good battery, no issues)
- **0.60-0.79**: Caution (moderate battery or minor issues)
- **0.40-0.59**: Warning (low battery or recurring breaches)
- **0.00-0.39**: Critical (very low battery or active breaches)

#### Step 6: Time-to-Breach Prediction (Lines 109-135)

The most sophisticated part of the algorithm.

**Goal**: Predict how many minutes until temperature crosses the threshold.

**Algorithm**:
1. Use last 5 readings (25 seconds of data)
2. Calculate slope (rate of change per 5-second interval)
3. Extrapolate to threshold
4. Apply 10% safety margin

**Implementation**:
```python
if len(history) >= 5:
    recent_delta = history[-1] - history[-5]  # Change over last 5 points
    avg_slope_per_reading = recent_delta / 4   # 4 intervals between 5 points
```

**Example: Heating Trend**:
```
Time    Temp
0s      4.0°C  (reading 1)
5s      4.2°C  (reading 2)
10s     4.4°C  (reading 3)
15s     4.7°C  (reading 4)
20s     5.0°C  (reading 5) ← Using last 5 readings

Δ = 5.0 - 4.0 = +1.0°C over 20 seconds
Slope per reading (5s) = 1.0 / 4 = +0.25°C per 5 seconds

Current temp = 5.0°C
Threshold (vaccines max) = 8.0°C
Degrees to go = 8.0 - 5.0 = 3.0°C

Readings needed = 3.0 / 0.25 = 12 readings
Minutes = (12 readings × 5 seconds) / 60 = 60 seconds = 1.0 minute

Apply safety margin (× 0.9): 1.0 × 0.9 = 0.9 minutes

Result: minutes_to_breach = 0.9
```

**Cold trend example**:
```
Current: 2.5°C, trending down at -0.3°C per reading
Threshold min = 2.0°C
Δ to threshold = 2.5 - 2.0 = 0.5°C
Readings needed = 0.5 / 0.3 = 1.67 readings
Time = 1.67 × 5s = 8.3s = 0.14 minutes
With safety margin: 0.14 × 0.9 = 0.1 minutes (6 seconds)

Result: minutes_to_breach = 0.1 (immediate danger!)
```

**When does prediction return -1?**
- Less than 5 readings available (warming up)
- No significant trend (slope ≈ 0)
- Already in breach state (we report actual breach, not future)

#### Step 7: Battery Life Prediction (Lines 137-155)

Predicts hours until battery depletes completely.

**Algorithm**:
```python
if s_id in last_battery:
    prev_batt = last_battery[s_id]
    drop_rate = prev_batt - battery  # % drop in last 5 seconds

    if drop_rate > 0:
        readings_per_hour = 720  # 12 readings/min × 60 min
        hours_until_dead = battery / (drop_rate × 720)
```

**Example**:
```
Battery now: 75.0%
Battery 5s ago: 75.1%
Drop rate = 0.1% per 5 seconds

Readings per hour = 720
Hourly drain = 0.1% × 720 = 72% per hour
Time to 0% = 75% / 72% per hour = 1.04 hours

Result: hours_until_dead = 1.0
```

**Realistic scenario**:
- Typical drain: 0.1% per reading
- Predicted life: 100% / (0.1 × 720) = 1.39 hours (83 minutes)
- Matches the simulator's battery model exactly

#### Step 8: Update Reading with Calculated Fields (Lines 157-162)

```python
reading["rolling_mean"] = round(avg_temp, 2)
reading["health_score"] = health
reading["is_breach"] = is_breach
reading["minutes_to_breach"] = minutes_to_breach
reading["hours_until_dead"] = hours_until_dead
```

**Enriched payload example**:
```json
{
  "sensor_id": "TEMP-001",
  "shipment_id": "SHP-2024-ABCD",
  "product_type": "vaccines",
  "timestamp": "2025-04-21T12:00:05.123456",
  "temperature_c": 9.2,
  "humidity_pct": 65.0,
  "battery_pct": 87.5,
  "rolling_mean": 8.45,
  "health_score": 0.73,
  "is_breach": true,
  "minutes_to_breach": -1,
  "hours_until_dead": 5.2
}
```

#### Step 9: Send to Dashboard API (Lines 164-168)

```python
try:
    requests.post(API_URL, json=reading, timeout=1)
except:
    pass  # Dashboard might be closed
```

- **Non-blocking**: If dashboard is down, subscriber continues
- **Timeout 1s**: Prevents backlog if dashboard is slow
- **JSON payload**: Sends enriched data with all calculated fields

#### Step 10: Write to InfluxDB (Lines 170-183)

```python
if writer:
    p = Point("sensor_reading") \
        .tag("sensor_id", s_id) \
        .tag("shipment_id", reading["shipment_id"]) \
        .tag("product_type", p_type) \
        .field("temperature_c", float(temp)) \
        .field("battery_pct", float(battery)) \
        .field("is_breach", bool(is_breach)) \
        .field("health_score", float(health)) \
        .field("minutes_to_breach", float(minutes_to_breach)) \
        .field("hours_until_dead", float(hours_until_dead))

    writer.write(bucket=BUCKET, record=p)
```

**InfluxDB data model**:
- **Measurement**: `sensor_reading`
- **Tags** (indexed for queries): `sensor_id`, `shipment_id`, `product_type`
- **Fields** (actual values): temperature, battery, scores, predictions

**Why use tags for sensor/shipment?**
Tags are indexed, making queries fast:
```sql
-- Query 1: All vaccine shipments in the last hour
from(bucket:"cold_chain")
  |> range(start: -1h)
  |> filter(fn: (r) => r.product_type == "vaccines")

-- Query 2: Last 24h for a specific sensor
from(bucket:"cold_chain")
  |> range(start: -24h)
  |> filter(fn: (r) => r.sensor_id == "TEMP-001")
```

### Section 4: MQTT Subscription Loop (Lines 185-197)

```python
subscriber = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
subscriber.on_message = process_message

subscriber.connect(BROKER, 1883)
subscriber.subscribe(TOPIC)
print("Subscriber is listening for sensor data...")
subscriber.loop_forever()
```

**MQTT Callback flow**:
```
MQTT message arrives
    ↓
paho-mqtt library receives it
    ↓
Calls process_message(client, userdata, message)
    ↓
Our logic processes & stores
    ↓
Returns to loop_forever() waiting for next message
```

## Full Data Pipeline Timeline

```
Timestamp    Event
────────────────────────────────────────────────────────
T+0s         subscriber.py starts
T+0s         Connects to MQTT broker
T+0s         Connects to InfluxDB
T+0s         Subscribes to "cold_chain/#"
T+5s         Sensor 1 publishes first reading
T+5.01s      MQTT delivers to subscriber
T+5.02s      process_message() called:
            - Parse JSON
            - Append to history (sensor_history[S1] = [4.0])
            - Calculate avg = 4.0
            - Check against profile → OK
            - health_score = 0.88
            - Send to dashboard API
            - Write to InfluxDB
T+5.05s      Returns to loop_forever()
T+10s        Sensor 1 publishes second reading
T+10.01s     process_message():
            - history = [4.0, 4.1]
            - avg = 4.05
            - check → OK
            - health = 0.88
            - dashboard + DB write
...
T+25s        Sensor 1: temp = 9.2°C (first breach)
            fail_count = 1 (no alert yet)
...
T+40s        Sensor 1: temp = 9.8°C (3rd consecutive breach)
            fail_count = 3 → ALERT!
            - send_push_notification() → ntfy.sh
            - is_breach = True
            - health_score drops to 0.24
...
T+60s        Sensor 1: temp = 7.5°C (back to normal)
            fail_count = 0 (recovery)
            - is_breach = False
```

## Real-World Example Walkthrough

**Scenario**: Vaccine shipment experiencing cooling failure

```
SENSOR CONFIG:
  sensor_id: "VAC-FRIGGE-01"
  shipment_id: "VAC-SHIP-2024-5678"
  profile: "vaccines"  → temp_min=2.0, temp_max=8.0

TIME    TEMP    HISTORY (last 12)      FAIL COUNT    ACTION
─────────────────────────────────────────────────────────────────
12:00   4.2°C   [4.2]                  0             OK, avg=4.2
12:05   4.3°C   [4.2, 4.3]             0             OK, avg=4.25
12:10   4.4°C   [4.2,4.3,4.4]          0             OK, avg=4.3
...     ...     ...                    0             Normal drift
12:30   4.8°C   [4.3,4.4,4.5,4.6,4.7,  0             OK, avg=4.55
                   4.8]
12:35   5.2°C   ... + new              0             OK, warming
12:40   6.1°C   ...                    0             Still OK
12:45   7.8°C   ...                    0             Near max (8.0°C)
12:50   9.2°C   [..., 4.8,5.2,6.1,7.8, 1             OUT OF RANGE
                   9.2]                               First failure
12:55   9.5°C   [..., 7.8,9.2,9.5]     2             Still OOR
13:00   9.8°C   [..., 9.2,9.5,9.8]     3             ★★★ ALERT ★★★
                                          → Push notification sent:
                                            "ALERT: VAC-FRIGGE-01 is too hot!
                                             Current: 9.8C"
                                          → is_breach = True
                                          → health_score drops
13:05   9.3°C   [..., 9.5,9.8,9.3]     4             Still in breach
13:10   8.5°C   [..., 9.8,9.3,8.5]     5             Still OOR
13:15   7.9°C   [..., 9.3,8.5,7.9]     6             Still OOR
13:20   7.2°C   [..., 8.5,7.9,7.2]     0             ★ RECOVERY ★
                                          → Back in range
                                          → fail_count reset to 0
                                          → is_breach = False
```

**Prediction Example** (at 12:50, when temp first hits 9.2°C):

History before spike: `[4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 5.2, 6.1, 7.8, 9.2]`
Recent 5-point trend: `[6.1, 7.8, 9.2]` → Δ = 3.1°C over 3 intervals
Slope ≈ 1.03°C per reading (5 seconds)
To go from 9.2°C to breach threshold (8°C already breached) → Already OOR
But if we caught it at 7.8°C at 12:45:
- Δ = 7.8 - 6.1 = 1.7°C over 15 seconds
- Slope = 1.7 / 3 = 0.57°C/reading
- To max (8.0°C): Δ_needed = 0.2°C
- Time = 0.2 / 0.57 = 0.35 readings = 1.75 seconds
- Safety margin × 0.9 = 1.6 seconds
- Prediction: `minutes_to_breach = 0.03` (essentially immediate)

**Battery Prediction** (at 12:50, battery 87%):
- 5 seconds ago: battery was 87.1%
- Drop rate = 0.1% per 5 seconds
- Hourly drain = 0.1% × 720 = 72% per hour
- Time to 0% = 87% / 72% ≈ 1.21 hours = 72 minutes
- `hours_until_dead = 1.2`

## Database Schema (InfluxDB)

**Measurement**: `sensor_reading`

| Column | Type | Description |
|--------|------|-------------|
| `sensor_id` | tag | Unique sensor identifier |
| `shipment_id` | tag | Associated shipment |
| `product_type` | tag | Product profile name |
| `temperature_c` | field | Current temperature in Celsius |
| `battery_pct` | field | Battery percentage (0-100) |
| `is_breach` | field | Boolean: currently violating thresholds |
| `health_score` | field | Overall health metric (0.0-1.0) |
| `minutes_to_breach` | field | Predicted minutes until threshold breach |
| `hours_until_dead` | field | Predicted hours until battery depletion |
| `_time` | timestamp | When reading was received (auto-generated) |

**Sample InfluxQL Query**:
```sql
-- Get all breaches in the last 24 hours
SELECT * FROM sensor_reading
WHERE is_breach = true
  AND time >= now() - 24h
```

**Sample Flux Query**:
```flux
from(bucket: "cold_chain")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "sensor_reading")
  |> filter(fn: (r) => r.sensor_id == "TEMP-001")
  |> filter(fn: (r) => r._field == "temperature_c")
  |> sort(columns: ["_time"], desc: false)
```

## Alert Logic Flowchart

```
┌───────────────────────────────────────────────────────────┐
│         Receive MQTT Message with Temperature            │
└─────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
              ┌─────────────────────────────┐
              │  Load profile for product   │
              │  e.g., vaccines: 2-8°C      │
              └─────────────┬───────────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │ Is temp < min OR > max?     │
              └─────────────┬───────────────┘
                            │
                 ┌──────────┴──────────┐
                 │                     │
                 ▼                     ▼
            ┌─────────┐         ┌─────────┐
            │   NO    │         │   YES   │
            └────┬────┘         └────┬────┘
                 │                   │
                 ▼                   ▼
        Reset fail_count        fail_count++
        is_breach = False       Is fail_count ≥ 3?
                                          │
                                 ┌────────┴────────┐
                                 │                 │
                                 ▼                 ▼
                           ┌─────────┐       ┌─────────┐
                           │  NO     │       │  YES    │
                           └────┬────┘       └────┬────┘
                                │                 │
                                ▼                 ▼
                        Don't alert yet   is_breach = True
                                         Send push notification
                                         Log alert to DB
```

## Dashboard API Integration

**Endpoint**: `POST http://127.0.0.1:8000/broadcast`

**Expected payload**:
```json
{
  "sensor_id": "TEMP-001",
  "shipment_id": "SHP-2024-ABCD",
  "product_type": "vaccines",
  "timestamp": "2025-04-21T12:00:05.123456",
  "temperature_c": 9.2,
  "humidity_pct": 65.0,
  "battery_pct": 87.5,
  "rolling_mean": 8.45,
  "health_score": 0.73,
  "is_breach": true,
  "minutes_to_breach": -1,
  "hours_until_dead": 5.2
}
```

**Expected response**: `200 OK` with acknowledgment

**If dashboard is down**: 
- Error is silently caught
- Subscriber continues (failsafe)
- Data still written to InfluxDB
- Dashboard can catch up on restart by querying InfluxDB

## Scaling & Performance

### Single-threaded but efficient
- Uses Paho's non-blocking `loop_forever()` internally
- Processes messages as they arrive
- Typical throughput: 100-1000 messages/second on modern hardware

### Memory usage
- `sensor_history`: 12 floats per active sensor ≈ 96 bytes
- `sensor_fail_counts`: 1 int per sensor ≈ 28 bytes
- `last_temperatures` / `last_battery`: 2 floats per sensor ≈ 32 bytes

**Example: 1000 sensors**
```
Total memory ≈ (96+28+32) × 1000 = 156 KB
+ Overhead ≈ 5-10 MB
```

### InfluxDB Write Patterns
- **Synchronous writes**: Each message waits for DB acknowledgment
- Throughput limited by DB performance (~10k writes/sec typical)
- Recommended: Batch writes if >100 sensors

## Error Handling & Resilience

| Failure Mode | Handling |
|--------------|----------|
| MQTT broker down | Prints error, retries connect (paho auto-reconnect) |
| InfluxDB down | Swallows exception, continues without DB writes |
| Dashboard down | Swallows exception, continues (data still in DB) |
| Invalid JSON | Would crash (no try-catch) - could add error handling |
| Missing fields | Uses `.get()` with defaults (battery=100, product=vaccines) |
| Profile not found | Falls back to `standard_vaccines` |

## Deployment Considerations

### As a Systemd Service (Linux)

`/etc/systemd/system/coldchain-subscriber.service`:
```ini
[Unit]
Description=Cold Chain Subscriber
After=network.target influxdb.service mosquitto.service

[Service]
Type=simple
User=coldchain
WorkingDirectory=/opt/cold_chain_monitor
ExecStart=/usr/bin/python3 subscriber/subscriber.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### As a Docker Container

`Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "subscriber/subscriber.py"]
```

### Environment Checklist

- [x] MQTT broker running (Mosquitto, EMQX, or HiveMQ)
- [x] InfluxDB instance accessible
- [x] `.env` file with credentials configured
- [x] Dashboard API running on port 8000 (or update `API_URL`)
- [x] `config/profiles.json` exists with product definitions

## Monitoring the Subscriber Itself

**Logs to watch**:
```
Database connected!
Subscriber is listening for sensor data...
[TEMP-001] Alert: High Temp Spike!  (from sensor_sim)
Push notification sent: ALERT: TEMP-001 is too hot! ...
```

**Health checks**:
```bash
# Check if process is running
ps aux | grep subscriber.py

# Check MQTT connectivity
mosquitto_sub -t "$SYS/#" -v

# Test database write (manually trigger sensor)
python simulator/sensor_sim.py
# Then query InfluxDB:
influx query 'from(bucket:"cold_chain") |> range(start: -1m)'
```

## Extending the Subscriber

### Add Humidity Checks

```python
# In process_message, after temperature check:
if reading["humidity_pct"] > rules["humidity_max"]:
    # Handle humidity breach...
```

### Add Multi-Sensor Correlation

```python
# Detect if ALL sensors in a shipment fail simultaneously
shipment_sensors = get_sensors_for_shipment(shipment_id)
if all(sensor_fail_counts.get(s, 0) >= MAX_FAILURES for s in shipment_sensors):
    send_critical_alert("ENTIRE SHIPMENT COMPROMISED")
```

### Add SMS Notifications (Twilio)

```python
from twilio.rest import Client

def send_sms(message):
    client = Client(ACCOUNT_SID, AUTH_TOKEN)
    client.messages.create(
        body=message,
        from_='+1234567890',
        to='+0987654321'
    )
```

## Summary

`subscriber.py` is a **mission-critical middleware** that:
- Bridges MQTT sensor network → InfluxDB → Dashboard
- Implements intelligent alerting with debouncing (3-strike rule)
- Predicts failures before they happen using linear extrapolation
- Tracks battery health to schedule sensor replacements
- Survives downstream failures without crashing

It's the glue that turns raw sensor data into actionable intelligence for cold chain operators.
