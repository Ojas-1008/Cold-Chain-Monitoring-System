import streamlit as st
import pandas as pd
import time
import os
import plotly.express as px
from influxdb_client import InfluxDBClient
from dotenv import load_dotenv

# 1. SETUP & CONFIGURATION
# Load environment variables (like our InfluxDB token)
load_dotenv()

# Database connection settings
URL = os.getenv("INFLUXDB_URL", "http://127.0.0.1:8086").replace("localhost", "127.0.0.1")
TOKEN = os.getenv("INFLUXDB_TOKEN")
ORG = os.getenv("INFLUXDB_ORG")
BUCKET = os.getenv("INFLUXDB_BUCKET")

# Page display settings
st.set_page_config(page_title="Cold Chain Monitor", page_icon="🧊", layout="wide")

# Initialize session state for reports if it doesn't exist
if "report_data" not in st.session_state:
    st.session_state.report_data = None

st.title("🧊 Cold Chain Fleet Monitor")
st.write("Real-time tracking for temperature-sensitive cargo")
st.markdown("---")

# 2. DATA FUNCTIONS

def get_live_data():
    """Fetches the last 1 hour of sensor readings from InfluxDB."""
    try:
        client = InfluxDBClient(url=URL, token=TOKEN, org=ORG)
        query_api = client.query_api()
        
        # Flux query to get data and turn fields into columns
        flux_query = f'''
            from(bucket: "{BUCKET}")
            |> range(start: -1h)
            |> filter(fn: (r) => r._measurement == "sensor_reading")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        
        df = query_api.query_data_frame(flux_query)
        client.close()
        
        if isinstance(df, list):
            if len(df) == 0: return pd.DataFrame()
            df = pd.concat(df, ignore_index=True)

        if df is None or df.empty:
            return pd.DataFrame()

        # Clean up the column names
        df = df.rename(columns={"_time": "timestamp"})
        
        # Remove internal InfluxDB columns that we don't need to see
        bad_cols = ["result", "table", "_start", "_stop", "_measurement"]
        df = df.drop(columns=bad_cols, errors="ignore")

        # Merge rows that have the same timestamp and sensor
        if "sensor_id" in df.columns:
            df = df.groupby(["timestamp", "sensor_id"], as_index=False).first()

        # Ensure we have a boolean for breaches
        if "is_breach" in df.columns:
            df["is_breach"] = df["is_breach"].fillna(False)

        return df
    except Exception as e:
        st.error(f"Error connecting to database: {e}")
        return pd.DataFrame()

def get_alerts():
    """Fetches breach events from the last 24 hours."""
    try:
        client = InfluxDBClient(url=URL, token=TOKEN, org=ORG)
        query_api = client.query_api()
        
        flux_query = f'''
            from(bucket: "{BUCKET}")
            |> range(start: -24h)
            |> filter(fn: (r) => r._measurement == "breach_event")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        
        df = query_api.query_data_frame(flux_query)
        client.close()
        
        if isinstance(df, list):
            if len(df) == 0: return pd.DataFrame()
            df = pd.concat(df, ignore_index=True)
            
        return df
    except:
        return pd.DataFrame()

def create_report(shipment_id):
    """Calculates summary stats for a shipment and saves a CSV."""
    try:
        client = InfluxDBClient(url=URL, token=TOKEN, org=ORG)
        query_api = client.query_api()
        
        query = f'''
            from(bucket: "{BUCKET}")
            |> range(start: -30d)
            |> filter(fn: (r) => r.shipment_id == "{shipment_id}")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        
        df = query_api.query_data_frame(query)
        client.close()
        
        if isinstance(df, list):
            df = pd.concat(df, ignore_index=True)
        
        if df.empty: return None

        # Sort by time so we can calculate durations
        df = df.sort_values("_time")
        
        # Calculate Average Temp
        avg_temp = df["temperature_c"].mean()

        # Calculate total breach time (assuming 5 seconds per reading)
        breaches = df[df["is_breach"] == True]
        breach_minutes = (len(breaches) * 5) / 60
        
        verdict = "PASS ✅" if breach_minutes == 0 else "FAIL ❌"

        # Save to CSV file
        os.makedirs("reports", exist_ok=True)
        filename = f"reports/{shipment_id}_report.csv"
        
        # Clean export data
        export_df = df.drop(columns=["result", "table", "_start", "_stop", "_measurement"], errors="ignore")
        export_df.to_csv(filename, index=False)
        
        return {
            "avg_temp": round(avg_temp, 2),
            "breach_mins": round(breach_minutes, 1),
            "verdict": verdict,
            "file": filename
        }
    except Exception as e:
        st.error(f"Report Error: {e}")
        return None

# 3. BUILD THE DASHBOARD UI

# Get the latest data
df = get_live_data()

if not df.empty:
    # --- Live Metrics for each sensor ---
    st.subheader("🚚 Active Fleet Status")
    all_sensors = df["sensor_id"].unique()
    grid = st.columns(len(all_sensors))
    
    for i in range(len(all_sensors)):
        s_id = all_sensors[i]
        last_reading = df[df["sensor_id"] == s_id].iloc[-1]
        
        temp = last_reading["temperature_c"]
        breach = last_reading["is_breach"]
        product = last_reading.get("product_type", "Unknown")
        # If the product name is missing (NaN), use "Unknown"
        if not isinstance(product, str):
            product = "Unknown"
        
        product = product.replace("_", " ").title()
        
        status = "🔴 BREACH" if breach else "🟢 SAFE"
        
        with grid[i]:
            st.metric(
                label=f"{product} ({s_id})",
                value=f"{temp}°C",
                delta=status,
                delta_color="normal" if not breach else "inverse"
            )

    st.markdown("---")

    # --- Charts ---
    st.subheader("📈 Temperature History (Last 1 Hour)")
    chart = px.line(
        df, 
        x="timestamp", 
        y="temperature_c", 
        color="sensor_id",
        template="plotly_dark",
        title="Real-time Sensor Movements"
    )
    st.plotly_chart(chart, use_container_width=True)

    # --- Details & Alerts ---
    left_col, right_col = st.columns(2)
    
    with left_col:
        st.subheader("📊 Sensor Statistics")
        # Simple groupby stats
        stats = df.groupby("sensor_id")["temperature_c"].agg(["mean", "min", "max"]).round(2)
        st.table(stats)
        
        st.subheader("🔋 Battery & Health")
        if "battery_pct" in df.columns:
            health = df.sort_values("timestamp").groupby("sensor_id")[["battery_pct", "health_score"]].last()
            st.dataframe(health, use_container_width=True)
        
    with right_col:
        st.subheader("🚨 Alert Log (Last 24h)")
        alerts_df = get_alerts()
        
        if alerts_df.empty:
            st.success("Everything is running normal!")
        else:
            # Show only important columns
            show_cols = ["_time", "sensor_id", "shipment_id", "temperature_c"]
            available = [c for c in show_cols if c in alerts_df.columns]
            st.dataframe(alerts_df[available].sort_values("_time", ascending=False).head(15), use_container_width=True)

    st.markdown("---")
    
    # --- Report Generation ---
    st.subheader("📋 Finalize Shipment")
    if "shipment_id" in df.columns:
        ids = df["shipment_id"].unique()
        choice = st.selectbox("Pick a shipment to close:", ids)
        
        if st.button("Generate Summary Report"):
            info = create_report(choice)
            if info:
                st.session_state.report_data = info
                st.session_state.active_shipment = choice

        # Show the report if it was generated
        if st.session_state.report_data:
            report = st.session_state.report_data
            st.write(f"### Report for {st.session_state.active_shipment}")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Result", report["verdict"])
            c2.metric("Average Temp", f"{report['avg_temp']}°C")
            c3.metric("Time in Breach", f"{report['breach_mins']} mins")
            
            with open(report["file"], "rb") as f:
                st.download_button("Download Full CSV Log", f, file_name=f"report_{choice}.csv")
            
            if st.button("Clear Report"):
                st.session_state.report_data = None
                st.rerun()
    else:
        st.write("No shipment data found yet.")

else:
    st.warning("Waiting for data... Please start your Simulator and Subscriber!")
    st.image("https://images.unsplash.com/photo-1580674285054-91550f40ad55?auto=format&fit=crop&w=800")

# --- AUTO REFRESH ---
# Refresh the page every 5 seconds to get new data
if st.session_state.report_data is None:
    time.sleep(5)
    st.rerun()

