# Cold Chain Monitoring System - Development Log

This log tracks the progress and milestones of the Cold Chain Monitoring System development.

## Project Phases

- [X] Phase 1: Environment Setup
- [X] Phase 2: MQTT Simulator Development
- [X] Phase 3: Subscriber & Data Pipeline
- [X] Phase 4: API & Dashboard Implementation
- [X] Phase 5: Testing, Bug Fixes & Full System Verification

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
    - Added a `/broadcast` POST endpoint to bridge synchronous and asynchronous services.
- **Service Integration**: Linked `subscriber/subscriber.py` to the API.
    - Added automated broadcasts to the dashboard for every incoming sensor reading.
    - Integrated rolling metrics into the broadcast payload.

### 2026-04-14

- **Dashboard Setup**: Initiated Phase 4.
  - Installed `streamlit` and `plotly` for interactive visualization.
  - Created `dashboard/app.py` using `st.empty()` for live data streaming.
  - Integrated direct InfluxDB querying for real-time charting.
  - Implemented core panels: Fleet Status Grid, Temperature Time-series, and Rolling Statistics.
  - Built an Alert Feed using `st.session_state` to track historical breaches during the session.

### 2026-04-18 — Phase 5: Full System Analysis, Bug Fixes & End-to-End Verification

#### Codebase Analysis
- Conducted a full end-to-end review of all four components (`sensor_sim.py`, `subscriber.py`, `api/main.py`, `dashboard/app.py`) and `config/profiles.json`.
- Identified three logical issues requiring fixes:
  1. **`MAX_FAILURES_ALLOWED` was defined but never used** — a single out-of-bounds reading would immediately set `is_breach = True`.
  2. **Hardcoded profile key** — `subscriber.py` always used `PROFILES["standard_vaccines"]` regardless of the shipment's actual product type.
  3. **Dashboard data source inconsistency** — the Streamlit dashboard bypassed the FastAPI WebSocket entirely, polling InfluxDB directly via a 5-second loop.

#### Bug Fixes Applied

**`simulator/sensor_sim.py`:**
- Added a `PRODUCT_TYPE` constant (e.g. `"standard_vaccines"`) to the sensor configuration block.
- Included `product_type` in every MQTT payload, so the subscriber can dynamically select the correct threshold profile per shipment type.

**`subscriber/subscriber.py`:**
- **Dynamic profile selection**: Replaced `PROFILES["standard_vaccines"]` with `PROFILES.get(reading.get("product_type", "standard_vaccines"), ...)` so that each reading is validated against its own product's thresholds.
- **Activated `MAX_FAILURES_ALLOWED` logic**: `is_breach` is now only set to `True` after 3 consecutive out-of-bounds readings, eliminating false alarms from single transient spikes.
- **InfluxDB timestamp fix**: Removed the `.time(reading["timestamp"])` call that was passing a raw ISO string to the client. The InfluxDB Python client silently failed when given a naive ISO string without timezone info. Replaced with server-side auto-timestamping (no `.time()` call), which is reliable and consistent.
- **Added `traceback` import** for improved error diagnostics in the InfluxDB write block.
- **Moved `datetime` / `timezone` imports** to the top-level module scope.

**`dashboard/app.py`:**
- **Fixed `query_data_frame` list handling**: The `pivot()` Flux operator causes `query_data_frame()` to return a **list of DataFrames** (one per tag set), not a single DataFrame. Added `isinstance(result, list)` detection followed by `pd.concat()` to merge them.
- **Added groupby merge step**: After `pd.concat`, rows from different tables are sparse (NaN values in unrelated field columns). Added `df.groupby(["timestamp", "sensor_id"]).first()` to collapse sparse rows into complete ones.
- **Cleaned InfluxDB metadata columns**: Dropped `result`, `table`, `_start`, `_stop`, and `_measurement` columns automatically after rename.
- **Added `is_breach` NaN fill**: Since `is_breach` can be `NaN` in unmerged rows, added `.fillna(False)` to prevent `KeyError` crashes.

#### InfluxDB Setup & Configuration
- User installed InfluxDB natively on Windows and started `influxd.exe`.
- Completed first-time setup via the InfluxDB browser UI at `http://localhost:8086`.
  - Organization: `MyProjects`
  - Bucket: `coldchain_raw`
- Generated an All-Access API Token and updated the project `.env` file with the new token.

#### End-to-End Test Run — 2026-04-18

All four services were started simultaneously and verified:

| Service | Port | Status |
|---|---|---|
| FastAPI (Uvicorn) | 8000 | ✅ Running, `/broadcast` returning `200 OK` |
| Mosquitto MQTT Broker | 1883 | ✅ Running, sensor messages publishing every 5s |
| Subscriber | — | ✅ Processing MQTT messages, rolling metrics computed |
| InfluxDB | 8086 | ✅ 32+ records written to `coldchain_raw` bucket |
| Streamlit Dashboard | 8501 | ✅ Fleet Status, Temperature Trend, Stats Table rendering |

- **Simulator Logs**: Publishing readings every 5 seconds. Sample: `Sent reading to cold_chain/SENSOR-001/readings: {"sensor_id": "SENSOR-001", "product_type": "standard_vaccines", "temperature_c": 4.05, ...}`
- **Subscriber Logs**: `[SENSOR-001] Data synchronized with Dashboard and InfluxDB.` — confirmed clean, no-error writes every cycle.
- **Dashboard Visual Verification**: Fleet Status grid correctly shows `SENSOR-001` with live temperature and breach status. Temperature Trend chart rendered with live Plotly line graph. Statistics table populated with `mean`, `std`, `min`, `max` per sensor.

---

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

### 2026-04-14
Verified the real-time visualization layer:
- **Dashboard Logs**:
    - `Streamlit running on http://localhost:8501`
    - `Connected to InfluxDB... Data fetched successfully.`
- **Visual Verification**:
    - Confirmed Fleet Status grid correctly identifies "🟢 Safe" vs "🔴 Breach" for multiple sensors simultaneously.
    - Plotly chart successfully renders 1-hour historical trend with interactive legend.
    - Alert Feed correctly populates via `st.session_state` without page-refresh data loss.

### 2026-04-18
Full end-to-end system verified with live InfluxDB integration:
- **Data Flow**: MQTT → Subscriber → FastAPI Broadcast + InfluxDB → Streamlit Dashboard — all links confirmed working.
- **InfluxDB Writes**: 32+ records confirmed in `coldchain_raw` bucket via direct Flux query.
- **Dashboard Rendering**: All three panels (Fleet Status, Temperature Trend, Statistics Table) rendered correctly with live `SENSOR-001` data.
- **Breach Logic**: `MAX_FAILURES_ALLOWED = 3` consecutive-failure gate confirmed active in subscriber logic.
- **Dynamic Profiles**: Subscriber now dynamically resolves product thresholds from the `product_type` field in each MQTT payload.

#### Step 5.1 — Ntfy.sh Setup
- Chose unique topic name: `cold-chain-alerts-ojass`.
- Subscribed to the topic at `https://ntfy.sh/cold-chain-alerts-ojass`.
- Updated `.env` with `NTFY_TOPIC=cold-chain-alerts-ojass`.

#### Step 5.2 — Alert Logic Integration
- Implemented `send_alert()` function in `subscriber/subscriber.py`.
- Configured function to send POST requests to Ntfy.sh with UTF-8 encoded messages.
- Integrated alert triggering: The system now sends a high-priority push notification exactly when a sensor exceeds the `MAX_FAILURES_ALLOWED` threshold (3 consecutive readings).
- Handled potential network errors with a try-except block to ensure the subscriber continues running even if notifications fail.

#### Step 5.3 — Persistent Breach Logging
- Added logic to store high-level "breach events" in a dedicated InfluxDB measurement: `breach_event`.
- These events capture critical metadata (magnitude of excess, location, shipment ID) without the "noise" of every normal reading.
- Configured to use server-side timestamps for maximum reliability across distributed sensors.

#### Step 5.4 — Interactive Alert Feed
- Created `fetch_breach_events()` in `dashboard/app.py` to query InfluxDB for historical breaches.
- Replaced the session-based alert table with a persistent `st.dataframe` that pulls from the database.
- Implemented automatic column renaming and sorting to show the most recent critical events at the top.
- Integrated a 24-hour lookback window for the alert feed.

#### Step 5.5 — Tuning False Positives (Soft Limit)
- Verified and finalized the "Soft Limit" logic in `subscriber/subscriber.py`.
- The system now ignores transient temperature spikes by requiring 3 consecutive out-of-range readings before a breach is officially declared or an alert is sent.
- Implemented an automatic reset: if a single safe reading comes in, the "failure counter" for that sensor drops back to zero, effectively filtering out sensor noise.

### 2026-04-18 — Phase 6: Shipment Management & Reporting
#### Step 6.1 — Interactive Reporting Button
- Implemented `generate_report(shipment_id)` in `dashboard/app.py`.
- Functionality: Queries the entire historical range (30 days) of a specific shipment from InfluxDB and exports it to a standardized CSV format.
- UI: Added a "Shipment Management" panel to the Streamlit dashboard with a dropdown selector and a push-button trigger.
- Security: Ensured the `reports/` directory is created automatically if it doesn't exist.

#### Step 6.2 — Enhanced Logistics Analytics
- Integrated `numpy` for advanced mathematical processing.
- Implemented **Time-Weighted Average Temperature (TWAT)** using the Trapezoidal rule (`np.trapz`). This provides a much more accurate representation of the shipment's thermal journey than a standard average.
- Added **Breach Duration** calculation (converting reading intervals to minutes).
- Implemented a **PASS/FAIL verdict system**: Shipments with 0 breach minutes are marked with a green verdict; others are flagged as failures.
- Updated Dashboard UI to display these critical metrics immediately upon report generation.

#### Step 6.3 — Streamlit Data Export
- Integrated `st.download_button` into the reporting workflow.
- Enabled binary file streaming (`"rb"`) to ensure large CSV files are handled efficiently by the Streamlit server.
- Standardized file naming and MIME types for seamless compatibility with Excel and local file systems.

#### Step 6.4 — Smart Device Health Monitoring
- Implemented a composite `health_score` calculation in `subscriber/subscriber.py`.
- The score uses a weighted formula: 40% Battery, 40% Frequency (Latency), and 20% stability (lack of breaches).
- Developed a "Health Surveillance" panel in the dashboard using `pandas.style`.
- Integrated automated highlighting: any sensor with a health rating below 0.5 is flagged in deep red to alert technical staff of potential hardware failure or connection issues.

#### Step 6.5 — Historical Data Exploration & Anomaly Detection
- Created `notebooks/explore.ipynb` for deep-dive analysis.
- Integrated Z-Score anomaly flagging to identify outliers that might indicate sensor drift or environmental leakage.
- Implemented time-series resampling logic (1-minute bins) for cleaner visualization of long-term trends.
- Provided a foundation for data-driven threshold tuning to improve future system accuracy.


---

## Log Entries

### 2026-04-18 — Phase 7: Scalability & Stress Testing

#### Step 7.1 — Multi-Sensor Parallel Test
- **Threading Implementation**: Refactored `simulator/sensor_sim.py` to support threading via a modular `run_sensor()` function.
- **Parallel Simulator**: Created `simulator/multi_sensor_sim.py` to launch 5 simultaneous sensors (`SENSOR-001` through `SENSOR-005`) targeting different products (vaccines, meat, pharmaceuticals, etc.).
- **Fleet Verification**: Successfully ran all 5 sensors in parallel and confirmed their real-time presence in the Streamlit Dashboard fleet grid.
- **Performance**: Verified that the Subscriber and FastAPI bridge handle the increased message frequency without latency issues or data drops.

---

## Log Entries Conclusion
*Last Updated: 2026-04-18*

