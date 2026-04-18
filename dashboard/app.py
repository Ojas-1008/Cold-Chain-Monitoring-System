import streamlit as st
import pandas as pd
import time
import os
import plotly.express as px
import numpy as np
from influxdb_client import InfluxDBClient
from dotenv import load_dotenv

# 1. LOAD CONFIGURATION
# explicitly point to the .env in the parent directory so it always finds the tokens
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=env_path)

# Windows can sometimes fail to parse "localhost" to IPv4 (it tries IPv6 by mistake)
# So we swap it strictly to 127.0.0.1
INFLUX_URL = os.getenv("INFLUXDB_URL", "http://127.0.0.1:8086").replace("localhost", "127.0.0.1")
INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUX_ORG = os.getenv("INFLUXDB_ORG")
INFLUX_BUCKET = os.getenv("INFLUXDB_BUCKET")

# 2. PAGE SETUP
st.set_page_config(
    page_title="Cold Chain Fleet Monitor",
    page_icon="🧊",
    layout="wide"
)

# Initialize Session State for Alerts
if "alerts" not in st.session_state:
    st.session_state.alerts = []

st.title("🧊 Cold Chain Logistics Fleet Monitor")
st.markdown("---")

# 3. DATABASE HELPER
def fetch_influx_data():
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query_api = client.query_api()
        
        # Pull last 1 hour of data, pivot metrics into columns
        query = f'''
            from(bucket: "{INFLUX_BUCKET}")
            |> range(start: -1h)
            |> filter(fn: (r) => r._measurement == "sensor_reading")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        
        result = query_api.query_data_frame(query)
        client.close()
        
        # query_data_frame can return a list of DataFrames (one per tag set)
        if isinstance(result, list):
            if len(result) == 0:
                return pd.DataFrame()
            df = pd.concat(result, ignore_index=True)
        else:
            df = result

        if df.empty:
            return pd.DataFrame()

        # Rename _time to timestamp and drop InfluxDB internal columns
        df = df.rename(columns={"_time": "timestamp"})
        cols_to_drop = [c for c in ["result", "table", "_start", "_stop", "_measurement"] if c in df.columns]
        df = df.drop(columns=cols_to_drop)

        # After concat, rows from different tables are sparse (NaNs in other field columns).
        # Group by timestamp + sensor_id and take first non-NaN value per group to merge them.
        if "sensor_id" in df.columns and "timestamp" in df.columns:
            df = df.groupby(["timestamp", "sensor_id"], as_index=False).first()

        # Fill boolean is_breach NaNs with False
        if "is_breach" in df.columns:
            df["is_breach"] = df["is_breach"].fillna(False)

        return df

    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

def fetch_breach_events():
    """Queries for critical breach events logged in the last 24 hours."""
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query_api = client.query_api()
        
        # Pull last 24h of breach events
        query = f'''
            from(bucket: "{INFLUX_BUCKET}")
            |> range(start: -24h)
            |> filter(fn: (r) => r._measurement == "breach_event")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        
        result = query_api.query_data_frame(query)
        client.close()
        
        if isinstance(result, list):
            if len(result) == 0: return pd.DataFrame()
            df = pd.concat(result, ignore_index=True)
        else:
            df = result
            
        return df
    except Exception:
        return pd.DataFrame()

def generate_report(shipment_id):
    """Queries journey history, calculates logistics metrics (TWAT, breaches), and saves log."""
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query_api = client.query_api()
        
        # Pull 30 days of history for this specific shipment
        query = f'''
            from(bucket: "{INFLUX_BUCKET}")
            |> range(start: -30d)
            |> filter(fn: (r) => r.shipment_id == "{shipment_id}")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        
        result = query_api.query_data_frame(query)
        client.close()
        
        if isinstance(result, list):
            if len(result) == 0: return None
            df = pd.concat(result, ignore_index=True)
        else:
            df = result
            
        if df.empty: return None

        # 1. PREPARE DATA
        df = df.sort_values("_time")
        df["timestamp_seconds"] = pd.to_datetime(df["_time"]).view('int64') / 1e9
        
        # 2. CALCULATE TIME-WEIGHTED AVG TEMP (TWAT)
        # This is more accurate than a simple average for uneven sensor intervals
        total_duration = df["timestamp_seconds"].iloc[-1] - df["timestamp_seconds"].iloc[0]
        if total_duration > 0:
            twat = np.trapz(df["temperature_c"], df["timestamp_seconds"]) / total_duration
        else:
            twat = df["temperature_c"].mean()

        # 3. CALCULATE BREACH SUMMARY
        # We assume each reading represents a 5-second window
        out_of_range = df[df["is_breach"] == True]
        total_breach_minutes = (len(out_of_range) * 5) / 60
        verdict = "PASS ✅" if total_breach_minutes == 0 else "FAIL ❌"

        # 4. EXPORT CSV
        df_export = df.rename(columns={"_time": "Timestamp"}).drop(columns=["timestamp_seconds"], errors="ignore")
        cols_to_drop = [c for c in ["result", "table", "_start", "_stop", "_measurement"] if c in df_export.columns]
        df_export = df_export.drop(columns=cols_to_drop)

        os.makedirs("reports", exist_ok=True)
        df_export.to_csv(f"reports/{shipment_id}_log.csv", index=False)
        
        return {
            "twat": round(twat, 2),
            "breach_mins": round(total_breach_minutes, 1),
            "verdict": verdict,
            "path": f"reports/{shipment_id}_log.csv"
        }
    except Exception as e:
        st.error(f"Report Error: {e}")
        return None

# 4. LIVE DASHBOARD LOOP
placeholder = st.empty()

while True:
    df = fetch_influx_data()
    
    with placeholder.container():
        if not df.empty:
            # --- PANEL 1: FLEET STATUS GRID ---
            st.subheader("🚚 Fleet Status")
            active_sensors = df["sensor_id"].unique()
            cols = st.columns(len(active_sensors))
            
            for col, sensor_id in zip(cols, active_sensors):
                # Get the latest data for this specific sensor
                sensor_data = df[df["sensor_id"] == sensor_id].iloc[-1]
                temp = sensor_data["temperature_c"]
                is_breach = sensor_data["is_breach"]
                product = sensor_data.get("product_type", "Unknown") # Get product name
                
                status_text = "🔴 Breach" if is_breach else "🟢 Safe"
                
                with col:
                    st.metric(
                        label=f"📦 {product.replace('_', ' ').title()} ({sensor_id})",
                        value=f"{temp}°C",
                        delta=status_text,
                        delta_color="normal" if not is_breach else "inverse"
                    )
                
                # Update Alert Feed if a breach is detected
                if is_breach:
                    # Check if we already logged this specific breach timestamp to avoid duplicates in the feed
                    new_alert = {"time": str(sensor_data["timestamp"]), "sensor": sensor_id, "reading": f"{temp}°C"}
                    if not st.session_state.alerts or st.session_state.alerts[-1] != new_alert:
                        st.session_state.alerts.append(new_alert)

            st.markdown("---")

            # --- PANEL 2: TEMPERATURE TIME-SERIES ---
            st.subheader("📈 Temperature Trend (Last 1h)")
            fig = px.line(
                df, 
                x="timestamp", 
                y="temperature_c", 
                color="sensor_id",
                title="Live Temperature Tracking by Sensor",
                template="plotly_dark",
                labels={"timestamp": "Time", "temperature_c": "Temp (°C)", "sensor_id": "Sensor"}
            )
            st.plotly_chart(fig, use_container_width=True)

            # --- PANEL 3: ANALYTICS & ALERTS ---
            col_stats, col_alerts = st.columns([1, 1])
            
            with col_stats:
                st.subheader("📊 Statistics Table")
                # Group by both ID and Product Name for clearer visualization
                group_cols = [c for c in ["sensor_id", "product_type"] if c in df.columns]
                stats_df = df.groupby(group_cols)["temperature_c"].agg(["mean", "std", "min", "max"]).round(2)
                st.dataframe(stats_df, use_container_width=True)
                
                st.subheader("🔋 Sensor Health")
                health_cols = [c for c in ["sensor_id", "battery_pct", "health_score"] if c in df.columns]
                # Get the latest health reading for each sensor
                health_df = df.sort_values("timestamp").groupby("sensor_id")[health_cols].last()
                
                # Apply styling: Red background if health_score < 0.5
                st.dataframe(
                    health_df.style.apply(
                        lambda x: ["background-color: #702121; color: white" if v < 0.5 else "" for v in x],
                        subset=["health_score"]
                    ),
                    use_container_width=True
                )
                
            with col_alerts:
                st.subheader("🚨 Persistent Alert Feed")
                alerts_df = fetch_breach_events()
                
                if alerts_df.empty:
                    st.success("✅ No breaches detected in last 24h")
                else:
                    # Rename columns for a cleaner display
                    if "_time" in alerts_df.columns:
                        display_df = alerts_df.rename(columns={
                            "_time": "Timestamp", 
                            "sensor_id": "Sensor ID",
                            "shipment_id": "Shipment", 
                            "temperature_c": "Breach Temp", 
                            "breach_magnitude": "Excess"
                        })
                        
                        st.dataframe(
                            display_df[["Timestamp", "Sensor ID", "Shipment", "Breach Temp", "Excess"]]
                            .sort_values("Timestamp", ascending=False)
                            .head(20),
                            use_container_width=True
                        )
                    else:
                        st.info("Breach data is still synchronizing...")

            st.markdown("---")
            
            # --- PANEL 4: SHIPMENT MANAGEMENT ---
            st.subheader("📋 Shipment Management")
            col_sel, col_btn = st.columns([3, 1])
            
            if "shipment_id" in df.columns:
                active_shipments = df["shipment_id"].unique()
                with col_sel:
                    selected_shipment = st.selectbox("Select Shipment to Finalize", active_shipments)
                
                with col_btn:
                    st.write(" ") # Padding for alignment
                    if st.button("Generate Report & End Shipment"):
                        with st.spinner("Processing logistics history..."):
                            report = generate_report(selected_shipment)
                            if report:
                                st.success(f"Log saved: {report['path']}")
                                # Show a quick summary to the user
                                m1, m2, m3 = st.columns(3)
                                m1.metric("Final Verdict", report["verdict"])
                                m2.metric("Avg. Temp (TWAT)", f"{report['twat']}°C")
                                m3.metric("Breach Duration", f"{report['breach_mins']}m")
                                
                                # Add Download Button for the CSV
                                with open(report["path"], "rb") as f:
                                    st.download_button(
                                        label="💾 Download Shipment Log (CSV)",
                                        data=f,
                                        file_name=f"{selected_shipment}_log.csv",
                                        mime="text/csv"
                                    )
                            else:
                                st.error("No historical data found for this ID.")
            else:
                st.warning("No shipment IDs found in the current data stream.")

        else:
            st.info("🔄 Waiting for sensor data... Ensure the Simulator and Subscriber are running.")
            st.image("https://images.unsplash.com/photo-1580674285054-91550f40ad55?q=80&w=2070&auto=format&fit=crop", caption="Awaiting Logistics Data")

    # Refresh every 5 seconds
    time.sleep(5)
