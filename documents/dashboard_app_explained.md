# Cold Chain Monitor - Streamlit Dashboard Application

## Overview

`dashboard/app.py` is a **real-time Streamlit web dashboard** that visualizes cold chain sensor data from InfluxDB. It displays live temperature readings, predictive breach warnings, historical trends, and generates compliance reports for temperature-sensitive shipments.

## Purpose

This dashboard provides operators with:

1. **Live Fleet Monitoring**: Real-time temperature status for all active sensors
2. **Predictive Alerts**: Warning before temperature thresholds are breached
3. **Historical Analysis**: Visual charts showing temperature trends over time
4. **Compliance Reporting**: Automated summary reports for shipment quality assurance
5. **Battery Health**: Predictive indicators for sensor maintenance

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Streamlit Dashboard                        │
│  (dashboard/app.py)                                             │
│                                                                 │
│  ┌─────────────┐   ┌──────────────────┐   ┌─────────────────┐  │
│  │  InfluxDB   │   │   API Endpoints  │   │  Sensor Network │
│  │  Database   │   │  (api/main.py)   │   │  (MQTT)         │
│  │  Port 8086  │◄──┼  WebSocket Push  │◄──┼  Simulator      │
│  └─────┬───────┘   └─────────┬────────┘   └────────┬────────┘  │
│        │                   │                        │          │
│        │ Query every refresh│ Real-time WebSocket   │ MQTT msgs │
│        │ (Flux)             │ (subscriber → API)    │           │
│        ▼                   │                        ▼          │
│  ┌─────────────────────────┴───────────────────────────────────┐│
│  │  Data Pipeline:                                              ││
│  │  1. Query InfluxDB every 5s (flux_query)                    ││
│  │  2. Clean & pivot data → Pandas DataFrame                   ││
│  │  3. Merge rows by timestamp & sensor_id                     ││
│  │  4. Calculate metrics & predictions                         ││
│  │  5. Render Streamlit components (metrics, charts, tables)   ││
│  │  6. Auto-refresh loop                                       ││
│  └──────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Technology Stack

- **Streamlit**: Web framework for data apps (Python-based, no frontend JS needed)
- **InfluxDB Client**: Time-series database query library
- **Pandas**: Data manipulation and aggregation
- **Plotly**: Interactive charts with dark theme

## Setup & Configuration (Lines 11-18)

```python
load_dotenv()  # Load .env file

URL = os.getenv("INFLUXDB_URL", "http://127.0.0.1:8086").replace("localhost", "127.0.0.1")
TOKEN = os.getenv("INFLUXDB_TOKEN")
ORG = os.getenv("INFLUXDB_ORG")
BUCKET = os.getenv("INFLUXDB_BUCKET")

st.set_page_config(page_title="Cold Chain Monitor", page_icon="🧊", layout="wide")
```

**Why replace localhost?**
- InfluxDB client has issues resolving `localhost` in some Docker/network setups
- Explicit `127.0.0.1` ensures connectivity

**`.env` file contents**:
```bash
INFLUXDB_URL=http://127.0.0.1:8086
INFLUXDB_TOKEN=your-token-here
INFLUXDB_ORG=cold_chain
INFLUXDB_BUCKET=cold_chain
```

## Product Profiles (Lines 28-37)

```python
def load_product_profiles():
    try:
        with open("config/profiles.json", "r") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Could not load thresholds: {e}")
        return {}

PROFILES = load_product_profiles()
```

Loads temperature thresholds for safety zone annotations:
- `vaccines`: min=2.0°C, max=8.0°C
- `fresh_produce`: min=1.0°C, max=6.0°C
- `frozen_foods`: min=-25.0°C, max=-15.0°C
- `pharmaceuticals`: min=15.0°C, max=25.0°C

## Data Fetching Functions

### 1. Live Data (Lines 45-87)

Queries the last 1 hour of sensor readings.

**Flux Query** (InfluxDB's SQL-like language):
```flux
from(bucket: "cold_chain")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "sensor_reading")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
```

**What pivot does**:
- InfluxDB stores each metric as a separate row
- Pivot combines fields (temp, battery, breach) into columns

**Before pivot**:
```
_time                | _field        | _value
2025-04-21T12:00:00Z | temperature_c | 4.2
2025-04-21T12:00:00Z | battery_pct   | 87.5
2025-04-21T12:00:00Z | is_breach     | false
```

**After pivot**:
```
_time                | temperature_c | battery_pct | is_breach
2025-04-21T12:00:00Z | 4.2           | 87.5        | false
```

**Processing steps**:
```python
# 1. Rename column for clarity
df = df.rename(columns={"_time": "timestamp"})

# 2. Drop internal InfluxDB columns
bad_cols = ["result", "table", "_start", "_stop", "_measurement"]
df = df.drop(columns=bad_cols, errors="ignore")

# 3. Merge rows with same timestamp & sensor (multi-field data)
df = df.groupby(["timestamp", "sensor_id"], as_index=False).first()

# 4. Ensure breach column is boolean
df["is_breach"] = df["is_breach"].fillna(False)
```

### 2. Alerts (Lines 89-111)

Queries breach events (stored separately as `breach_event` measurement).

```flux
from(bucket: "cold_chain")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "breach_event")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
```

*Note: The current code references `breach_event`, but subscriber.py only writes to `sensor_reading`. This is a potential mismatch.*

### 3. Report Generation (Lines 113-162)

Creates CSV summary for a specific shipment.

**Query** (last 30 days for one shipment):
```flux
from(bucket: "cold_chain")
  |> range(start: -30d)
  |> filter(fn: (r) => r.shipment_id == "VAC-SHIP-123")
  |> pivot(...)
```

**Calculations**:
```python
avg_temp = df["temperature_c"].mean()

breaches = df[df["is_breach"] == True]  # Rows where breach = True
breach_minutes = (len(breaches) * 5) / 60  # 5 sec per reading

verdict = "PASS ✅" if breach_minutes == 0 else "FAIL ❌"
```

**Example**: 500 readings, 30 breaches → 30 × 5s = 150s = 2.5 minutes → FAIL ❌

## Dashboard UI Components

### Header (Lines 39-41)

```python
st.title("🧊 Cold Chain Fleet Monitor")
st.write("Real-time tracking for temperature-sensitive cargo")
st.markdown("---")
```

### Live Metrics Grid (Lines 166-211)

Displays a metric card for each active sensor.

```python
all_sensors = df["sensor_id"].unique()  # e.g., ['TEMP-001', 'TEMP-002']
grid = st.columns(len(all_sensors))

for i in range(len(all_sensors)):
    s_id = all_sensors[i]
    last_reading = df[df["sensor_id"] == s_id].iloc[-1]
    
    # Extract status
    breach = last_reading["is_breach"]
    prediction = last_reading.get("minutes_to_breach", -1)
    
    # Determine label & color
    if breach:
        status = "🔴 BREACH"
        color = "inverse"  # Red
    elif 0 < prediction < 120:  # Breach in < 2 hours
        status = f"⚠️ BREACH IN {prediction}m"
        color = "off"  # Orange-ish
    else:
        status = "🟢 SAFE"
        color = "normal"  # Green
    
    # Display metric
    with grid[i]:
        st.metric(
            label=f"{product_label} ({s_id})",
            value=f"{temp}°C",
            delta=status,
            delta_color=color
        )
```

**Example metric card**:
```
┌──────────────────────────────┐
│  Vaccines (TEMP-001)         │
│     9.2°C                    │
│  🔴 BREACH                   │
└──────────────────────────────┘
```

Status colors in Streamlit:
- `normal` = **green text** (good)
- `inverse` = **red text** (alert)
- `off` = **neutral/gray** (warning)

### Temperature History Chart (Lines 215-255)

Interactive line chart with safety zones.

```python
chart = px.line(
    df, 
    x="timestamp", 
    y="temperature_c", 
    color="sensor_id",
    template="plotly_dark",
    title="Real-time Sensor Movements"
)

# Add horizontal lines for each product's limits
for prod_type in active_products:
    if prod_type in PROFILES:
        limits = PROFILES[prod_type]
        
        # Upper limit (red dashed line)
        chart.add_hline(
            y=limits["temp_max"], 
            line_dash="dash", 
            line_color="red",
            annotation_text=f"{label_name} MAX ({limits['temp_max']}°C)"
        )
        
        # Lower limit (cyan dashed line)
        chart.add_hline(
            y=limits["temp_min"], 
            line_dash="dash", 
            line_color="cyan",
            annotation_text=f"{label_name} MIN ({limits['temp_min']}°C)"
        )
```

**Safety zones example**:
```
Temp (°C)
  25 ┤────────────────────────────────────────┐ Pharmaceuticals MAX (25°C)
     │                                        │
  15 ├────────────────────────────────────────┤ Pharmaceuticals MIN (15°C)
     │                                        │
   8 ├────────────────────────────────────────┤ Vaccines MAX (8°C)    ────┐
     │       ╭─╮                             │                           │
   6 ├───────╯ ╰──────────────────────────────┤ Fresh Produce MAX (6°C)   │
     │                                        ├──────────────────────────┤
   2 ├────────────────────────────────────────┤ Vaccines MIN (2°C)        │ Safe zone
     │                                        ├──────────────────────────┤ for vaccines
   1 ├────────────────────────────────────────┤ Fresh Produce MIN (1°C)   │
     │                                        │                           │
  -5 ┼                                        │                           │
     └────────────────────────────────────────┴───────────────────────────┘
           ↑          ↑            ↑           ↑
       Sensor A   Sensor B     Sensor C      Sensor D
```

The chart shows which sensors are in/out of range. Sensors breaching limits appear outside the safe zones.

### Statistics Table (Lines 260-264)

Simple Pandas aggregation:

```python
stats = df.groupby("sensor_id")["temperature_c"].agg(["mean", "min", "max"]).round(2)
st.table(stats)
```

**Output**:
```
              mean    min    max
sensor_id
TEMP-001     4.23   2.01   9.20
TEMP-002     5.12   3.45   7.88
```

### Battery & Predictions Table (Lines 266-280)

Shows latest battery level and predictive metrics.

```python
cols = ["battery_pct", "hours_until_dead", "health_score", "minutes_to_breach"]
latest_info = df.sort_values("timestamp").groupby("sensor_id")[cols].last()

# Format hour value
latest_info["Hours Until Dead"] = latest_info["Hours Until Dead"].apply(
    lambda x: f"{x}h" if x > 0 else "Calculating..."
)
```

**Example row**:
```
                 Battery Pct  Hours Until Dead  Health Score  Minutes To Breach
sensor_id
TEMP-001              87.5              5.2h          0.73                 -1
TEMP-002              92.1           Calculating       0.88                 45
```

Interpretation:
- `Hours Until Dead`: How long until battery depletes (for maintenance planning)
- `Health Score`: 0-1 (higher = healthier)
- `Minutes To Breach`: Positive = time until breach, -1 = safe/no trend

### Category Analysis Chart (Lines 284-300)

Bar chart showing total breaches per product type.

```python
category_stats = df.groupby("product_type")["is_breach"].sum().reset_index()

fig = px.bar(
    category_stats, 
    x="product_type", 
    y="is_breach",
    title="Risk Level by Product Category"
)
```

**Example**: If vaccines had 5 breaches, produce had 0:
```
Risk Level by Product Category
│
│  🔴 Vaccines: 5
│  🟢 Fresh Produce: 0
│  🟢 Frozen Foods: 0
```

### Alert Log (Lines 302-311)

Displays recent breaches from `breach_event` measurement.

```python
alerts_df = get_alerts()

if alerts_df.empty:
    st.success("Everything is running normal!")
else:
    st.dataframe(alerts_df[available_cols].sort_values("_time", ascending=False).head(15))
```

Shows the last 15 breaches with timestamp, sensor, shipment, and temperature.

### Report Generation (Lines 315-342)

Interactive report creation for closing shipments.

```python
ids = df["shipment_id"].unique()
choice = st.selectbox("Pick a shipment to close:", ids)

if st.button("Generate Summary Report"):
    info = create_report(choice)
    if info:
        st.session_state.report_data = info
```

**Report includes**:
- ✅/❌ Pass/Fail verdict
- Average temperature
- Total time in breach (minutes)
- Downloadable CSV of all raw data

**Session state** preserves the report across auto-refreshes.

## Auto-Refresh Mechanism (Lines 351-354)

```python
if st.session_state.report_data is None:
    time.sleep(5)
    st.rerun()
```

**How it works**:
1. Dashboard loads
2. Data is fetched and displayed
3. Pause 5 seconds (`time.sleep(5)`)
4. `st.rerun()` reloads entire script
5. New data is fetched
6. Repeat

**Why 5 seconds?**
- Matches sensor broadcast interval
- Fast enough for "real-time" feel
- Slow enough to not overload DB or browser

**During report viewing**: Auto-refresh pauses so users can interact with the report.

## Full User Workflow Example

### Scenario: Monitoring Vaccine Shipment

**1. System starts**
```bash
# Terminal 1: Start simulator
python simulator/sensor_sim.py

# Terminal 2: Start subscriber
python subscriber/subscriber.py

# Terminal 3: Start dashboard
streamlit run dashboard/app.py
```

**2. Dashboard loads** (`http://localhost:8501`)
```
┌────────────────────────────────────────────────────────┐
│ Cold Chain Fleet Monitor                                 │
├────────────────────────────────────────────────────────┤
│ 🟢 SAFE  (TEMP-001)    Vaccines: 4.2°C                  │
│ 🟢 SAFE  (TEMP-002)    Vaccines: 5.1°C                  │
│                                                     [⬥] │
├────────────────────────────────────────────────────────┤
│ Temperature History (Last 1 Hour)                       │
│                                                        │
│    10 +                                           ┐      │
│     8 +                                       ┐   │      │
│     6 +                                   ┐   │   │      │
│ Temp 4 + ────────────────────────────┐   │   │   │      │
│     2 +                           │   │   │   │   ┐  │      │
│     0 +                           │   │   │   │   │  │      │
│        └─┬──┬──┬──┬──┬──┬──┬──┬──┬─┘   │   │   │   │  │      │
│          12:00  12:15  12:30  12:45 13:00 13:15 13:30│      │
│                  Vaccines MAX (8°C) ───────────────────┴─────┤ red
│                  Vaccines MIN (2°C) ─────────────────────────┴┤ cyan
└───────────────────────────────────────────────────────────────┘
```

**3. Temperature spike detected** (TEMP-001 reaches 9.2°C)
- After 3 consecutive failures (~15 seconds), subscriber sends alert
- Dashboard metric changes:
  ```
  🔴 BREACH  (TEMP-001)    9.2°C
  ```
- The line on the chart crosses the red MAX line → visual alert
- Alert log shows new entry

**4. Recovery** (temperature drops to 7.5°C)
```
🟢 SAFE  (TEMP-001)    7.5°C
```

**5. Shipment complete → Generate report**
- User selects shipment from dropdown
- Clicks "Generate Summary Report"
- Dashboard shows:
  ```
  ┌────────────┬───────────────┬──────────────────┐
  │ Result     │ PASS ✅       │                  │
  │ Avg Temp   │ 5.2°C         │                  │
  │ Breach Min │ 2.5 mins      │                  │
  └────────────┴───────────────┴──────────────────┘
  [ Download Full CSV Log ]  [ Clear Report ]
  ```

## Handling Edge Cases

### No Data Scenario (Lines 346-348)

```python
else:
    st.warning("Waiting for data... Please start your Simulator and Subscriber!")
    st.image("https://images.unsplash.com/photo-1580674285054-91550f40ad55?auto=format&fit=crop&w=800")
```

Shows helpful message if query returns empty DataFrame.

### Missing Columns

```python
if "shipment_id" in df.columns:
    # Show report section
else:
    st.write("No shipment data found yet.")
```

Gracefully handles missing data fields (e.g., old data format without certain columns).

### Database Connection Error (Lines 85-86)

```python
except Exception as e:
    st.error(f"Error connecting to database: {e}")
    return pd.DataFrame()
```

Displays red error box in Streamlit UI if database is unreachable.

### Product Type Cleanup (Lines 183-184)

```python
product = last_reading.get("product_type", "Unknown")
if not isinstance(product, str):
    product = "Unknown"  # Handle NaN values
```

Converts NaN to "Unknown" to prevent display errors.

## Performance Optimizations

1. **Data deduplication**: `groupby` merges rows for same timestamp/sensor
2. **Query limiting**: Fetch only last 1 hour for live view
3. **Batch updates**: All metrics computed in single DataFrame pass
4. **Efficient aggregation**: Pandas `groupby` is vectorized (C-speed)

## Dependencies

`requirements.txt` (likely):
```
streamlit>=1.0
pandas>=1.5
plotly>=5.0
influxdb-client>=1.36
dotenv>=0.19
```

Install with:
```bash
pip install -r requirements.txt
```

## Running the Dashboard

```bash
# Basic
streamlit run dashboard/app.py

# Specific port
streamlit run dashboard/app.py --server.port 8501

# Headless (no browser auto-open)
streamlit run dashboard/app.py --server.headless true
```

## URL Parameters

Streamlit supports URL-based configuration:
- `?theme=dark` - Force dark mode
- `?embed=true` - Embed mode (hides Streamlit chrome)

## Customization Points

### Change Refresh Rate

```python
time.sleep(5)  # Change to 10 for slower, 2 for faster
```

### Add New Product Type

1. Edit `config/profiles.json`
2. Chart auto-updates (queries `profiles.json` at runtime)

### Add New Metric to Table

Add to `latest_info` columns list:
```python
cols = ["battery_pct", "hours_until_dead", "health_score", "minutes_to_breach", "new_column"]
```

### Change Chart Theme

```python
chart = px.line(..., template="plotly_white")  # or "seaborn", "ggplot2"
```

## Limitations & Known Issues

1. **Auto-refresh clears state**: When `st.rerun()` fires, all Streamlit widgets reset
   - **Mitigation**: Use `st.session_state` for report data (already done)

2. **Query overlap**: Each refresh re-queries last 1 hour; data may appear twice if refresh is slow
   - **Mitigation**: Acceptable for monitoring (shows latest values)

3. **Breach events query**: References `breach_event` measurement that subscriber doesn't create
   - **Fix needed**: Either subscriber should log breaches separately, or query should filter `sensor_reading` where `is_breach=true`

4. **No authentication**: Anyone with URL can see data
   - **Production**: Add `st.session_state` auth check or use Streamlit Enterprise auth

## Comparison to Pure Frontend (React/Vue)

| Feature | Streamlit | React/Vue |
|---------|-----------|----------|
| Development speed | ⚡⚡⚡ Fast (Python only) | Slower (need frontend + backend) |
| Custom UI control | Limited (Streamlit components) | Full (any HTML/CSS/JS) |
| Real-time | Polling (refresh loop) | WebSockets (instant) |
| Learning curve | Low (Python) | Higher (JS ecosystem) |
| Deployment | Simple (Python any host) | Needs build step, serves static files |
| Interactivity | Moderate (buttons, inputs) | High (full SPA capabilities) |

## Summary

`dashboard/app.py` is a **turn-key monitoring dashboard** that:
- Queries InfluxDB every 5 seconds for live data
- Renders metrics, charts, and tables with automatic refresh
- Highlights breaches and predicts future issues
- Generates compliance reports for audit trails
- Requires zero frontend knowledge to maintain

It's ideal for rapid deployment of monitoring tools and can evolve into a more sophisticated React app if needed, but provides immediate value with minimal code.
