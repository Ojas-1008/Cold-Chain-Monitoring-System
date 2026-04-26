# Cold Chain Sensor Simulator - Technical Documentation

## Overview

`sensor_sim.py` is a Python-based IoT sensor simulator that mimics real-world temperature and humidity monitoring devices used in cold chain logistics. It generates realistic sensor data, simulates equipment malfunctions, and publishes readings to an MQTT broker for consumption by monitoring systems.

## Purpose

This simulator serves several critical roles in the cold chain monitoring ecosystem:

1. **Testing & Development**: Allows developers to test the monitoring system without physical hardware
2. **Demo & Training**: Provides realistic data for stakeholder demonstrations
3. **Load Testing**: Can simulate multiple simultaneous sensors to test system scalability
4. **Edge Case Simulation**: Intentionally triggers alarm conditions to test alerting logic

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Sensor Simulator Process                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐                                           │
│  │  Configuration  │── Gets sensor ID, shipment, product type   │
│  │   Dictionary    │                                           │
│  └─────────────────┘                                           │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              MAIN SIMULATION LOOP                       │   │
│  │  (Repeats every 5 seconds)                              │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │ 1. Gradual temp drift: ±0.1°C                          │   │
│  │ 2. Random spike (5% chance): +2 to +5°C or -2 to -5°C │   │
│  │ 3. Battery drain: -0.1% per cycle                       │   │
│  │ 4. Build JSON payload                                   │   │
│  │ 5. Publish to MQTT topic                                │   │
│  └─────────────────────────────────────────────────────────┘   │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              MQTT Broker (localhost:1883)               │   │
│  │  Topic: cold_chain/{sensor_id}/readings                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │        Monitoring System (subscribes to topics)         │   │
│  │  - Validates against profile thresholds                  │   │
│  │  - Triggers alerts if thresholds breached                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Code Walkthrough

### Configuration & Imports (Lines 1-11)

```python
import time              # For sleep delays between readings
import json              # To format sensor data as JSON
import random            # For realistic data variation
from datetime import datetime  # For accurate timestamps
import paho.mqtt.client as mqtt  # MQTT communication library
```

**Settings**:

- `MQTT_BROKER`: Local MQTT server address
- `MQTT_PORT`: Standard MQTT port (1883)
- `TOPIC_BASE`: Base topic for all cold chain messages

### The `run_sensor()` Function

This is the core function that runs each simulated sensor.

#### Step 1: Parse Configuration (Lines 13-16)

```python
name = config.get("id", "S-000")           # Unique sensor identifier
shipment = config.get("shipment", "Unknown")  # Associated shipment ID
product = config.get("profile", "vaccines")   # Product type for threshold selection
```

**Example config dictionary**:

```python
{
    "id": "TEMP-001",
    "shipment": "SHP-2024-ABCD",
    "profile": "fresh_produce"
}
```

#### Step 2: Initialize Sensor State (Lines 18-21)

```python
temp = 4.0          # Starting temperature in Celsius
humidity = 50.0     # Starting humidity percentage
battery = 100.0     # Starting battery level (fully charged)
```

Each sensor starts at normal room temperature with full battery.

#### Step 3: MQTT Connection (Lines 24-31)

```python
client = mqtt.Client()
client.connect(MQTT_BROKER, MQTT_PORT)
```

The sensor connects to the local MQTT broker. If Mosquitto (or another MQTT server) isn't running, the simulator exits with an error message.

**MQTT** (Message Queue Telemetry Transport) is a lightweight messaging protocol ideal for IoT devices with limited bandwidth.

#### Step 4: Main Loop - Data Simulation (Lines 35-73)

The loop runs indefinitely until interrupted (Ctrl+C).

**4a. Gradual Temperature Drift** (Line 37)

```python
temp = temp + random.uniform(-0.1, 0.1)
```

- Adds a small random value between -0.1°C and +0.1°C
- Simulates normal thermal fluctuations in a refrigerated environment
- Example sequence: 4.00 → 4.03 → 3.97 → 4.08 → 4.02...

**4b. Random Temperature Spikes** (Lines 39-48)

```python
if random.random() < 0.05:  # 5% chance per cycle
    if random.random() < 0.7:  # 70% hot spike
        temp = temp + random.uniform(2, 5)
    else:  # 30% cold spike
        temp = temp - random.uniform(2, 5)
```

**Simulates malfunctions**:

- **Hot spike (70%)**: Cooling unit failure, door left open, compressor malfunction
  - Example: 4.0°C → 8.5°C (sudden increase)
- **Cold spike (30%)**: Thermostat bug, over-cooling, refrigerant leak
  - Example: 4.0°C → -0.5°C (risk of freezing vaccines)

**Frequency calculation**:

- Checked every 5 seconds
- 5% chance × 20 cycles/minute = ~1 spike per 4 minutes
- Over 1 hour: ~15 spikes total

**4c. Battery Drain** (Lines 51-52)

```python
battery = battery - 0.1
```

- Each 5-second cycle uses 0.1% battery
- Rate: 0.1% per 5 seconds = 1.2% per minute = 72% per hour
- Battery would deplete from 100% to 0% in ~83 minutes (realistic for actual IoT sensors)
- At 0%, real sensors would stop transmitting (low-battery alerts typically sent at 20%)

**4d. Build JSON Payload** (Lines 55-63)

```python
data = {
    "sensor_id": name,              # e.g., "TEMP-001"
    "shipment_id": shipment,        # e.g., "SHP-2024-ABCD"
    "product_type": product,        # e.g., "vaccines"
    "timestamp": datetime.now().isoformat(),
    "temperature_c": round(temp, 2),      # e.g., 5.37
    "humidity_pct": round(humidity, 2),   # e.g., 62.0
    "battery_pct": round(battery, 2)      # e.g., 87.5
}
```

**Example output JSON**:

```json
{
  "sensor_id": "TEMP-001",
  "shipment_id": "SHP-2024-ABCD",
  "product_type": "vaccines",
  "timestamp": "2025-04-21T12:34:56.789012",
  "temperature_c": 6.82,
  "humidity_pct": 78.34,
  "battery_pct": 94.2
}
```

**4e. Publish to MQTT** (Lines 66-70)

```python
json_string = json.dumps(data)  # Convert dict to JSON string
topic = f"{TOPIC_BASE}/{name}/readings"  # e.g., "cold_chain/TEMP-001/readings"
client.publish(topic, json_string)
```

**MQTT Topic Structure**:

```
cold_chain/
├── TEMP-001/readings
├── TEMP-002/readings
├── HUMID-001/readings
└── ...
```

**Why hierarchical topics?**

- Easy subscription: Subscribe to `cold_chain/#` for all sensors
- Filtering: Subscribe to `cold_chain/TEMP-+/readings` for all temperature sensors
- Organization: Natural grouping by sensor type

#### Step 5: Sleep Interval (Line 73)

```python
time.sleep(5)  # Pause 5 seconds before next reading
```

**Why 5 seconds?**

- Frequent enough to catch rapid temperature changes
- Not so frequent that it overwhelms the network or broker
- Typical for monitoring systems (1-60 seconds is common)
- Balances battery life with data resolution

### Graceful Shutdown (Lines 75-77)

```python
except KeyboardInterrupt:
    print(f"[{name}] Stopping...")
    client.disconnect()
```

Press Ctrl+C to stop the simulator cleanly. This disconnects from MQTT and prevents "connection lost" errors in other services.

### Standalone Execution (Lines 80-82)

```python
if __name__ == "__main__":
    test_config = {"id": "TEST-1", "shipment": "SHP-1", "profile": "vaccines"}
    run_sensor(test_config)
```

Allows the script to be run directly:

```bash
python simulator/sensor_sim.py
```

## Real-World Simulation Accuracy

### What This Simulates Well

| Aspect            | Realism | Notes                                                                |
| ----------------- | ------- | -------------------------------------------------------------------- |
| Temperature drift | High    | ±0.1°C matches actual sensor precision                             |
| Spike events      | Medium  | Real faults are more correlated (e.g., door open → gradual warming) |
| Battery drain     | High    | 1.2%/min is realistic for frequent transmissions                     |
| Humidity          | Static  | Real sensors would also have humidity drift                          |
| Network issues    | None    | No simulated packet loss or disconnections                           |

### What It Doesn't Simulate

- Sensor calibration drift over time
- Multiple sensors in the same unit averaging to false stability
- Physical sensor failures (stuck readings)
- Network latency, duplicate messages, or MQTT QoS levels
- Power cycles or reboots
- Time synchronization issues

## Usage Examples

### Example 1: Running a Single Vaccine Sensor

```bash
python simulator/sensor_sim.py
```

**Output**:

```
[TEST-1] Connected to Broker.
[TEST-1] Sent: {"sensor_id": "TEST-1", "shipment_id": "SHP-1", "product_type": "vaccines", "timestamp": "2025-04-21T12:00:05.123456", "temperature_c": 4.23, "humidity_pct": 50.0, "battery_pct": 99.9}
[TEST-1] Alert: High Temp Spike!
[TEST-1] Sent: {"sensor_id": "TEST-1", "shipment_id": "SHP-1", "product_type": "vaccines", "timestamp": "2025-04-21T12:00:10.234567", "temperature_c": 8.67, "humidity_pct": 50.0, "battery_pct": 99.8}
```

### Example 2: Multiple Sensors via multi_sensor_sim.py

The project likely includes a `multi_sensor_sim.py` that runs multiple instances:

```python
sensors = [
    {"id": "VAC-001", "shipment": "VAC-2024-001", "profile": "vaccines"},
    {"id": "PRO-001", "shipment": "PRO-2024-001", "profile": "fresh_produce"},
    {"id": "FRO-001", "shipment": "FRO-2024-001", "profile": "frozen_foods"},
]

for sensor_config in sensors:
    run_sensor(sensor_config)  # Would need threading/multiprocessing
```

### Example 3: MQTT Subscriber (Testing)

Subscribe to see data in real-time:

```bash
# Using mosquitto_sub (install Mosquitto tools)
mosquitto_sub -t "cold_chain/+/readings" -v
```

**Output**:

```
cold_chain/TEMP-001/readings {"sensor_id": "TEMP-001", ...}
cold_chain/HUMID-001/readings {"sensor_id": "HUMID-001", ...}
```

## Data Flow Timeline

```
Time    Event
0s      Simulator starts, connects to MQTT broker
0s      Initial state: temp=4.0°C, humidity=50%, battery=100%
5s      First reading sent: temp=4.03°C, battery=99.9%
10s     Second reading: temp=3.97°C, battery=99.8%
15s     Spike! temp jumps to 7.82°C (hot spike), battery=99.7%
20s     Recovery: temp=6.1°C, battery=99.6%
...     Continues every 5 seconds
83min   Battery reaches 0% (if never interrupted)
```

## Integration with Monitoring System

The monitoring application (likely in `src/` or `app/`) subscribes to MQTT topics:

```python
# Pseudocode for monitoring system
def on_message(client, userdata, msg):
    payload = json.loads(msg.payload)
    profile = load_profile(payload["product_type"])

    # Check against thresholds
    if payload["temperature_c"] < profile["temp_min"]:
        send_alert("LOW_TEMP", payload)
    elif payload["temperature_c"] > profile["temp_max"]:
        send_alert("HIGH_TEMP", payload)

    if payload["humidity_pct"] > profile["humidity_max"]:
        send_alert("HIGH_HUMIDITY", payload)
```

**Alert Logic Example**:

```
Received: temp=9.2°C, product_type=vaccines, profile=standard_vaccines
Profile limits: min=2.0, max=8.0
Result: ❌ ALERT - Temperature exceeds maximum (8.0°C)
```

## Security Considerations (Production)

This simulator is for development/testing only. Production IoT devices should implement:

1. **Authentication**: MQTT username/password or TLS client certificates
2. **Encryption**: Use MQTT over TLS (port 8883) to prevent eavesdropping
3. **Authorization**: Topic ACLs to restrict publish/subscribe permissions
4. **Message integrity**: Payload signatures to prevent tampering
5. **Firmware signing**: Secure boot for physical devices

## Conclusion

`sensor_sim.py` provides a realistic, configurable foundation for cold chain monitoring system development. By mimicking actual IoT sensor behavior—including gradual drift, random failures, and battery depletion—it enables thorough testing of alerting logic and dashboards before deploying to production.
