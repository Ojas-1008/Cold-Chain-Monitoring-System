# Running the Cold Chain Monitoring System

Follow these steps in order to start the complete monitoring pipeline.

## Prerequisites

1.  **MQTT Broker**: Ensure an MQTT broker (like Mosquitto) is installed and running on `localhost:1883`.
2.  **InfluxDB**: Ensure InfluxDB is installed and the `influxd.exe` server is running.
3.  **Environment Variables**: Ensure your `.env` file is updated with the correct InfluxDB Token, Org, and Bucket.

---

## 🚀 One-Click Start (Recommended)
The easiest way to start the entire system is using the provided batch script. It will now automatically launch **InfluxDB** and all 4 services in separate windows:

1.  Make sure your **MQTT Broker** (Mosquitto) is already running in the background.
2.  Double-click `run_all.bat` in the project root.
3.  Or run it from the terminal:
    ```powershell
    .\run_all.bat
    ```

---

## Step-by-Step Execution (Manual)
If you prefer to start them manually, open a separate terminal window for each:

### 0. Start InfluxDB
Required for data storage.
```powershell
& "C:\Users\ojass\Downloads\influxd.exe"
```

### 1. Start the FastAPI Backend
This service handles real-time data broadcasting via WebSockets.
```powershell
.\venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```
*Accessible at: http://127.0.0.1:8000*

### 2. Start the Data Subscriber
This service listens to MQTT messages, calculates analytics, and saves data to InfluxDB.
```powershell
.\venv\Scripts\python.exe subscriber\subscriber.py
```

### 3. Start the Sensor Simulator
This service generates simulated temperature and humidity data for multiple sensors.
```powershell
.\venv\Scripts\python.exe simulator\multi_sensor_sim.py
```

### 4. Start the Streamlit Dashboard (Frontend)
This provides the visual monitoring interface.
```powershell
.\venv\Scripts\python.exe -m streamlit run dashboard\app.py
```
*Accessible at: http://localhost:8501*

---

## Service Overview

| Component | Responsibility | Port |
| :--- | :--- | :--- |
| **InfluxDB** | Permanent Data Storage | 8086 |
| **MQTT Broker** | Message Transport | 1883 |
| **FastAPI** | Real-time Broadcast (WS) | 8000 |
| **Streamlit** | User Interface | 8501 |

## Troubleshooting

*   **InfluxDB Connection Refused**: Check if `influxd.exe` is running and the port in `.env` matches.
*   **MQTT Connection Failed**: Ensure your MQTT broker service is started.
*   **Module Not Found**: Ensure you are running commands from the project root with the virtual environment activated.
