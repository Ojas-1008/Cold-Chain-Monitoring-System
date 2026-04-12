# Cold Chain Monitoring System - Development Log

This log tracks the progress and milestones of the Cold Chain Monitoring System development.

## Project Phases

- [X] Phase 1: Environment Setup
- [ ] Phase 2: MQTT Simulator Development
- [ ] Phase 3: Subscriber & Data Pipeline
- [ ] Phase 4: API & Dashboard Implementation
- [ ] Phase 5: Testing & Documentation

---

## Log Entries

### 2026-04-12

- **Project Initialization**: Created the base directory structure.
  - `api/`
  - `config/`
  - `notebooks/`
  - `reports/`
  - `simulator/`
  - `subscriber/`
- **Virtual Environment**: Set up a Python virtual environment (`venv`) for dependency isolation.
- **Dependency Installation**: Installed core Python libraries:
  - `paho-mqtt` (MQTT Connectivity)
  - `faker` (Simulated Data Generation)
  - `fastapi` & `uvicorn` (Web Framework & Server)
  - `influxdb-client` (Time-series Database)
  - `pandas` & `numpy` (Data Processing)
  - `apscheduler` (Scheduling Tasks)
  - `requests` (HTTP Client)
- **Tracking**: Created `DEVELOPMENT_LOG.md` to document the journey.

### 2026-04-12 (Continued)

- **Configuration Setup**: Defined product threshold profiles in `config/profiles.json`.
  - Added profiles for vaccines, fresh produce, frozen foods, and pharmaceuticals.
- **Source Control**: Initialized Git repository and pushed to [GitHub](https://github.com/Ojas-1008/Cold-Chain-Monitoring-System).
- **Simulator Development**: Created `simulator/sensor_sim.py`.
    - Implemented random data generation with drift and spike modeling.
    - Simplified code to beginner-level procedural logic.
- **Subscriber Development & Data Pipeline**: 
    - Created `subscriber/subscriber.py` with beginner-friendly procedural logic.
    - **Security**: Implemented `.env` for securing InfluxDB tokens and credentials.
    - **Threshold Logic**: Added magnitude calculation and "Soft Limit" (3-consecutive failure) alert logic.
    - **Metrics**: Integrated `pandas` to calculate rolling mean, standard deviation, and rate of change (`dT/dt`) in real-time.
    - **Storage**: Standardized storage in InfluxDB with accurate sensor-side timestamps.
- **Project Maturity**: Established `.gitignore` best practices for Python and secrets.
- **API Development**: Created `api/main.py`.
    - Initialized FastAPI server with WebSocket support (`/ws` endpoint).
    - Implemented a "Broadcast" system to track and update connected dashboard clients in real-time.
    - Simplified code to beginner-level procedural logic for educational clarity.

## Test Run Results & Verification

### 2026-04-12
Successfully ran an end-to-end verification of the data pipeline:
- **Subscriber Logs**:
    - `Loading product profiles... Profiles loaded successfully!`
    - `Connected to InfluxDB!`
    - `Waiting for data and computing rolling metrics...`
    - `[SENSOR-001] Temp: 3.99C | Avg(12): 4.07C | Delta: -0.02C`
- **Simulator Logs**:
    - `Connected to localhost successfully!`
    - `Sent reading to cold_chain/SENSOR-001/readings: {...}`
- **Metrics Verification**: Confirmed that `rolling_mean` and `rate_of_change` are correctly calculated and stored in InfluxDB after the 12-reading buffer is filled.
