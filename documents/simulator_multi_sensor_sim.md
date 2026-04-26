# Understanding `multi_sensor_sim.py`

## What This File Does

This file is a **fleet simulator wrapper**. It runs multiple sensor simulators at the same time, each simulating a different cargo shipment with different product types.

Think of it like a **train station** - instead of one train (sensor), we now have multiple trains (sensors) all running on different tracks simultaneously.

---

## Purpose

In the real world, a cold chain monitoring system would track many cargo trucks/shipments at once. This file simulates that by running **4 different sensors** in parallel:

| Sensor ID | Shipment | Product Type | Safe Temp Range |
|----------|----------|--------------|-----------------|
| SENSOR-001 | SHP-ALPHA | vaccines | 2°C - 8°C |
| SENSOR-002 | SHP-BETA | food | 1°C - 6°C |
| SENSOR-003 | SHP-GAMMA | meat | -1°C - 4°C |
| SENSOR-004 | SHP-DELTA | medicine | 15°C - 25°C |

---

## How It Works (Step-by-Step)

### Step 1: Import Modules
```python
import threading
import time
from sensor_sim import run_sensor
```

- `threading` - Python's built-in module for running multiple tasks simultaneously
- `time` - For adding delays between sensor startups
- `run_sensor` - The single sensor function from `sensor_sim.py`

### Step 2: Define the Sensor List
```python
sensor_list = [
    {"id": "SENSOR-001", "shipment": "SHP-ALPHA", "profile": "vaccines"},
    {"id": "SENSOR-002", "shipment": "SHP-BETA", "profile": "food"},
    {"id": "SENSOR-003", "shipment": "SHP-GAMMA", "profile": "meat"},
    {"id": "SENSOR-004", "shipment": "SHP-DELTA", "profile": "medicine"},
]
```

Each item is a **configuration dictionary** with:
- `id` - Unique sensor identifier
- `shipment` - Cargo shipment ID
- `profile` - Product type (determines temperature limits)

### Step 3: Start Each Sensor in a New Thread
```python
for config in sensor_list:
    thread = threading.Thread(target=run_sensor, args=(config,))
    thread.daemon = True
    thread.start()
    time.sleep(1)
```

**Key Concept: Threading**

A thread is like a separate "worker" that runs alongside the main program. Here's what happens:

```
Main Program:
    ├── Thread 1: SENSOR-001 running → publishes temp data every 5s
    ├── Thread 2: SENSOR-002 running → publishes temp data every 5s
    ├── Thread 3: SENSOR-003 running → publishes temp data every 5s
    └── Thread 4: SENSOR-004 running → publishes temp data every 5s
```

- `threading.Thread(target=run_sensor, args=(config,))` - Creates a new thread that will run the `run_sensor` function with the config as input
- `thread.daemon = True` - This ensures threads stop automatically when the main program stops
- `thread.start()` - Actually starts the thread running
- `time.sleep(1)` - Waits 1 second before starting the next sensor (prevents overwhelming the broker)

### Step 4: Keep the Program Running
```python
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nShutting down sensors...")
```

The main program enters an infinite loop, keeping itself alive so the threads can continue running. When you press Ctrl+C, it breaks out of the loop.

---

## Visual Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    multi_sensor_sim.py                       │
├─────────────────────────────────────────────────────────────────┤
│                                                          │
│  sensor_list[]                                           │
│  ┌──────────┬──────────┬──────────┬──────────┐         │
│  │ SENSOR-  │ SENSOR-  │ SENSOR-  │ SENSOR-  │         │
│  │  001    │  002    │  003    │  004    │         │
│  └────┬────┴────┬────┴────┬────┴────┬────┘         │
│       │         │         │         │                   │
│       ▼         ▼         ▼         ▼                   │
│  ┌─────────────────────────────────────┐              │
│  │     threading.Thread() x 4            │              │
│  │     (runs run_sensor in parallel)     │              │
│  └──────────────────┬──────────────────┘              │
│                     │                                   │
│                     ▼                                   │
│              MQTT Broker                                 │
│              ┌──────────┐                               │
│              │localhost │                               │
│              │ :1883    │                               │
│              └──────────┘                               │
│                     │                                   │
│     ┌───────────────┼───────────────┐                   │
│     │               │               │                   │
│     ▼               ▼               ▼                   │
│  Topic:           Topic:          Topic:                │
│  cold_chain/      cold_chain/     cold_chain/          │
│  SENSOR-001/     SENSOR-002/     SENSOR-003/          │
│  readings        readings        readings               │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## Comparison: Single vs Multi Sensor

### Using `sensor_sim.py` directly (Single Sensor)
```bash
python simulator/sensor_sim.py
# Only one sensor runs at a time
```

### Using `multi_sensor_sim.py` (Multiple Sensors)
```bash
python simulator/multi_sensor_sim.py
# All 4 sensors run simultaneously
```

---

## What This Produces

When you run this file, you'll see output like:

```
Starting Fleet Simulation...
Started SENSOR-001
Started SENSOR-002
Started SENSOR-003
Started SENSOR-004

All sensors are running!
Press Ctrl+C to stop the simulation.

[SENSOR-001] Connected to Broker.
[SENSOR-001] Sent: {"temperature_c": 4.23, ...}
[SENSOR-002] Connected to Broker.
[SENSOR-002] Sent: {"temperature_c": 5.12, ...}
[SENSOR-003] Connected to Broker.
[SENSOR-003] Sent: {"temperature_c": 2.45, ...}
[SENSOR-004] Connected to Broker.
[SENSOR-004] Sent: {"temperature_c": 18.67, ...}
...
```

Each sensor runs independently, publishing its own temperature readings to different MQTT topics:
- `cold_chain/SENSOR-001/readings`
- `cold_chain/SENSOR-002/readings`
- `cold_chain/SENSOR-003/readings`
- `cold_chain/SENSOR-004/readings`

---

## Key Takeaways

1. **Threading** allows multiple sensors to run simultaneously without blocking each other
2. Each sensor gets its own **configuration** (ID, shipment, product type)
3. The `daemon=True` flag ensures threads cleanup automatically
4. The MQTT broker receives data from all sensors on different topics
5. This file is the "multiplier" - turning one sensor into a whole fleet