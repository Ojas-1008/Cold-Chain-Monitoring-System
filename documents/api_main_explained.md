# Cold Chain API - Real-Time WebSocket Server

## Overview

`api/main.py` is a lightweight **FastAPI** web server that acts as a real-time data broadcaster, pushing sensor readings from the cold chain monitoring system to connected web dashboards via WebSockets. It bridges the gap between the backend processing (subscriber) and frontend visualization (dashboard).

## Purpose

This API server has three core responsibilities:

1. **Ingest** processed sensor data via HTTP POST from the subscriber
2. **Broadcast** that data instantly to all connected dashboard clients via WebSocket
3. **Maintain** persistent WebSocket connections and handle client lifecycle

## Architecture & Data Flow

```
┌─────────────┐
│ sensor_sim  │  (MQTT)
└──────┬──────┘
       │ MQTT messages
       ▼
┌─────────────────────┐
│   MQTT Broker       │
│  (localhost:1883)   │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────────────────────────────┐
│      subscriber.py                         │
│  • Receives MQTT                            │
│  • Validates against profiles.json          │
│  • Calculates predictions & health scores   │
│  • Writes to InfluxDB                       │
│  • POSTs to this API →                      │
│    POST http://localhost:8000/broadcast     │
└──────────────────────┬──────────────────────┘
                       │ HTTP POST
                       ▼
┌─────────────────────────────────────────────┐
│        api/main.py (FastAPI)                │
│  ┌─────────────────────────────────────────┐│
│  │  POST /broadcast                        ││
│  │  ← Receives enriched sensor data         ││
│  │  ← For each connected WebSocket client: ││
│  │    → await client.send_json(data)       ││
│  └─────────────────────────────────────────┘│
│                        │                    │
│                        │ WebSocket push     │
│                        ▼                    │
│  ┌─────────────────────────────────────────┐│
│  │  WebSocket /ws                          ││
│  │  ← Accepts dashboard connections        ││
│  │  ← Maintains connected_clients list     ││
│  │  ← Keeps connections alive with ping    ││
│  └─────────────────────────────────────────┘│
└──────────────────────┬──────────────────────┘
                       │ WebSocket
                       ▼
┌─────────────────────────────────────────────┐
│      Web Dashboard (React/Vue/HTML)         │
│  • Connects: ws://localhost:8000/ws         │
│  • Listens for JSON messages                │
│  • Updates UI in real-time                  │
│  • Displays charts, alerts, metrics         │
└─────────────────────────────────────────────┘
```

## Complete Data Pipeline

```
┌──────────┐   MQTT    ┌──────────┐   MQTT    ┌─────────────┐   HTTP    ┌──────────┐   WS    ┌────────────┐
│ Sensor   │──────────▶│ Broker   │──────────▶│ Subscriber  │─────────▶│  API     │────────▶│Dashboard  │
│ Simulator│           │ Mosquitto│           │(processor)  │ POST     │(FastAPI) │ Push    │(Browser)  │
└──────────┘           └──────────┘           └─────────────┘          └──────────┘          └────────────┘
     │                      │                      │                       │                      │
     │ Publishes            │ Routes               │ Processes             │ Receives             │ Listens
     │ JSON:                │ messages             │ & enriches            │ /broadcast           │ on /ws
     │ {temp: 4.2, ...}     │ to all               │ {temp:4.2,            │ {temp:4.2, ...}      │ Updates
     │                      │ subscribers          │  health:0.88, ...}    │                      │ charts
```

## Code Walkthrough

### Imports (Lines 1-2)

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
```

**FastAPI**: Modern Python web framework with automatic API docs, async support, and WebSocket capabilities.

**CORSMiddleware**: Allows cross-origin requests (needed if dashboard is served from a different port/domain).

### Application Setup (Lines 4-11)

```python
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Allow any origin (development only!)
    allow_methods=["*"],       # Allow all HTTP methods
    allow_headers=["*"]        # Allow all headers
)
```

**Why CORS?**

- Dashboard likely runs on port 3000 (React) or 5173 (Vite)
- API runs on port 8000
- Browsers block cross-origin HTTP requests by default
- CORS middleware adds `Access-Control-Allow-Origin: *` header

**⚠️ Security Note**:
`allow_origins=["*"]` is OK for development but **dangerous in production**. Lock it down:

```python
# Production example:
allow_origins=[
    "https://dashboard.coldchain.com",
    "http://localhost:3000"  # Development
]
```

### Global State (Line 14)

```python
connected_clients = []
```

**A list of active WebSocket connections**.

Example after 3 dashboards connect:

```python
connected_clients = [
    <WebSocket id=1 ip=192.168.1.100>,   # Dashboard at office
    <WebSocket id=2 ip=10.0.0.50>,       # Mobile dashboard
    <WebSocket id=3 ip=127.0.0.1:55031>  # Developer browser
]
```

**⚠️ Thread-safety note**: FastAPI runs async event loop, but `connected_clients` is accessed from:

- `/broadcast` POST endpoint (may be called concurrently)
- `/ws` WebSocket endpoint (accept & disconnect)
- The list operations are atomic in CPython's GIL, but for production scale consider:
  - `asyncio.Lock()` around list modifications
  - Using a `set()` instead of `list()` for O(1) removal

### Health Check Endpoint (Lines 16-18)

```python
@app.get("/")
def home():
    return {"status": "API is online"}
```

**Simple liveness probe**:

```bash
curl http://localhost:8000/
# Response: {"status":"API is online"}
```

**Used by**:

- Load balancers to check if API is alive
- Orchestration systems (Kubernetes, Docker Compose) for health checks
- Developers debugging connectivity

### Broadcast Endpoint (Lines 20-29)

The heart of the data ingestion pipeline.

```python
@app.post("/broadcast")
async def receive_data(data: dict):
    for client in connected_clients:
        try:
            await client.send_json(data)
        except:
            pass  # If client broken, ignore (WebSocket loop removes it)
    return {"message": "Data shared!"}
```

**How it works**:

1. **Receives POST request** from subscriber with JSON body

   ```
   POST http://localhost:8000/broadcast
   Content-Type: application/json

   {
     "sensor_id": "TEMP-001",
     "temperature_c": 9.2,
     ...
   }
   ```
2. **Iterates over all connected WebSocket clients**

   ```python
   for client in connected_clients:
   ```
3. **Sends the data to each client asynchronously**

   ```python
   await client.send_json(data)
   ```

   - `await`: Non-blocking; yields control while data transmits
   - If client buffer full or connection dead, raises exception
4. **Error handling**: Silently ignores failed sends (the WebSocket disconnect handler cleans up dead connections)
5. **Returns acknowledgment**

   ```json
   {"message": "Data shared!"}
   ```

**Example flow**:

```
1. Dashboard A connects → connected_clients = [A]
2. Dashboard B connects → connected_clients = [A, B]
3. POST /broadcast received
   → send to A: ✓
   → send to B: ✓
4. Dashboard B disconnects (closes tab)
5. POST /broadcast received
   → send to A: ✓
   → send to B: ✗ (Connection closed)
   → exception caught, ignored
6. WebSocket loop detects B's disconnect → removes B from list
   → connected_clients = [A]
```

**Performance characteristics**:

- **Time to broadcast** to N clients: O(N)
- Example: 100 clients, each send takes 10ms → ~1 second total
- For higher scale, consider:
  - Fan-out via Redis Pub/Sub
  - Message broker (RabbitMQ, NATS)
  - Server-Sent Events (SSE) instead of WebSocket

### WebSocket Endpoint (Lines 31-45)

The persistent connection handler for dashboards.

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
  
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
```

**Connection lifecycle**:

**Step 1: Accept connection**

```python
await websocket.accept()
```

- Completes WebSocket handshake
- Sends 101 Switching Protocols response
- Connection upgrades from HTTP to WebSocket

**Step 2: Register client**

```python
connected_clients.append(websocket)
```

Now the client will receive broadcasts.

**Step 3: Keep connection alive**

```python
while True:
    await websocket.receive_text()
```

**Why receive messages if we only send?**

- WebSocket is bidirectional; both sides can send
- We read (and discard) incoming messages to:
  - Detect if client disconnects (raises `WebSocketDisconnect`)
  - Keep TCP connection alive (prevents timeout)
  - Allow future extensions (client could send commands/config)

**Alternative implementation** (heartbeat pattern):

```python
import asyncio

async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
  
    try:
        while True:
            # Wait for ping or client message (timeout after 60s)
            data = await asyncio.wait_for(websocket.receive_text(), timeout=60)
            # Could handle client messages here
    except asyncio.TimeoutError:
        pass  # Client silent too long, disconnect
    finally:
        connected_clients.remove(websocket)
```

**Step 4: Handle disconnect**

```python
except (WebSocketDisconnect, Exception):
    pass
finally:
    if websocket in connected_clients:
        connected_clients.remove(websocket)
```

**Cleanup is critical** to prevent:

- Memory leaks (dangling references to dead sockets)
- Errors when trying to send to closed connections
- `connected_clients` list growing indefinitely

### Full Request/Response Cycle

**Dashboard JavaScript** (connecting & listening):

```javascript
const ws = new WebSocket("ws://localhost:8000/ws");

ws.onopen = () => console.log("Connected to API");

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Received:", data);
  updateDashboard(data);  // Your UI update function
};

ws.onclose = () => console.log("Disconnected");
```

**Subscriber POST** (sending data):

```python
import requests

payload = {
    "sensor_id": "TEMP-001",
    "temperature_c": 9.2,
    "product_type": "vaccines",
    ...
}

response = requests.post("http://localhost:8000/broadcast", json=payload)
print(response.json())  # {"message": "Data shared!"}
```

**What the dashboard receives**:
Same `payload` dict, delivered as WebSocket message:

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

## API Endpoints Summary

| Method | Path           | Purpose                        | Request Body         | Response                       |
| ------ | -------------- | ------------------------------ | -------------------- | ------------------------------ |
| GET    | `/`          | Health check                   | None                 | `{"status":"API is online"}` |
| POST   | `/broadcast` | Ingest sensor data & broadcast | Sensor JSON          | `{"message":"Data shared!"}` |
| WS     | `/ws`        | Real-time dashboard streaming  | (binary/text frames) | Continuous JSON stream         |
