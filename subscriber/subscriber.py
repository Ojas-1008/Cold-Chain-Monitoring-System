import json
import paho.mqtt.client as mqtt
import os
import pandas as pd
import requests
import traceback
from collections import deque
from datetime import datetime, timezone
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# Load the .env file to get our secret tokens
load_dotenv()

# --- CONFIGURATION ---
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "cold_chain/#"

# API Settings for real-time dashboard broadcasting
API_URL = "http://localhost:8000/broadcast"

# InfluxDB Settings (Reading from .env)
INFLUX_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUX_ORG = os.getenv("INFLUXDB_ORG")
INFLUX_BUCKET = os.getenv("INFLUXDB_BUCKET")

# --- ALERT & HISTORY SETTINGS ---
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "cold-chain-alerts-ojass")
MAX_FAILURES_ALLOWED = 3
sensor_fail_counts = {}
HISTORY_SIZE = 12
sensor_history = {}
sensor_last_time = {} # Track time of last reading for frequency score

# --- LOAD THRESHOLDS ---
print("Loading product profiles...")
with open("config/profiles.json", "r") as f:
    PROFILES = json.load(f)
print("Profiles loaded successfully!")

# --- SETUP INFLUXDB ---
try:
    influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = influx_client.write_api(write_options=SYNCHRONOUS)
    print("Connected to InfluxDB!")
except Exception as e:
    print(f"Warning: Could not connect to InfluxDB. Error: {e}")
    write_api = None

# --- ALERTING FUNCTION ---
def send_alert(reading, breach_magnitude, profile):
    """Sends a push notification via ntfy.sh when a breach is detected."""
    message = (
        f"⚠️ BREACH: {reading['sensor_id']} | "
        f"Temp: {reading['temperature_c']}°C | "
        f"Limit: {profile['temp_max']}°C | "
        f"Excess: {breach_magnitude:.2f}°C"
    )
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": "Cold Chain Breach", "Priority": "high"},
            timeout=5
        )
        print(f"!!! Alert sent to Ntfy topic: {NTFY_TOPIC} !!!")
    except Exception as e:
        print(f"Failed to send Ntfy alert: {e}")

# --- MESSAGE HANDLER ---
def on_message(client, userdata, message):
    payload = message.payload.decode()
    reading = json.loads(payload)
    
    sensor_id = reading["sensor_id"]
    temp = reading["temperature_c"]
    humidity = reading["humidity_pct"]
    
    # --- 1. TRACK HISTORY FOR PANDAS ---
    if sensor_id not in sensor_history:
        sensor_history[sensor_id] = deque(maxlen=HISTORY_SIZE)
    sensor_history[sensor_id].append(temp)
    
    # --- 2. CALCULATE ROLLING METRICS ---
    history_list = list(sensor_history[sensor_id])
    df = pd.DataFrame(history_list, columns=["temp"])
    
    rolling_mean = 0.0
    rolling_std = 0.0
    rate_of_change = 0.0
    
    if len(history_list) >= 2:
        rate_of_change = df["temp"].diff().iloc[-1]
    if len(history_list) == HISTORY_SIZE:
        rolling_mean = df["temp"].mean()
        rolling_std = df["temp"].std()
    
    # --- 3. CALCULATE HEALTH SCORE ---
    # a) Battery Score (0.0 to 1.0)
    battery_score = reading.get("battery_pct", 100) / 100

    # b) Frequency Score (Did it arrive on time? Expected every 5s)
    current_time = datetime.now(timezone.utc)
    freq_score = 1.0
    if sensor_id in sensor_last_time:
        diff = (current_time - sensor_last_time[sensor_id]).total_seconds()
        if diff > 7: # If delayed by more than 2s (5s + 2s slack)
            freq_score = 0.5 
    sensor_last_time[sensor_id] = current_time

    # c) Stability Score (How many recent readings were NOT breaches?)
    safe_count = 0
    for h_temp in history_list:
        # Check if history temp was within standard range (simplified)
        if 2 <= h_temp <= 8: safe_count += 1
    stability_score = safe_count / len(history_list) if len(history_list) > 0 else 1.0

    # Final Weighted Health Score
    health_score = (0.4 * battery_score) + (0.4 * freq_score) + (0.2 * stability_score)
    health_score = round(float(health_score), 2)

    # --- 4. CHECK THRESHOLDS ---
    profile_key = reading.get("product_type", "standard_vaccines")
    profile = PROFILES.get(profile_key, PROFILES["standard_vaccines"])
    is_breach = False
    
    if temp > profile["temp_max"] or temp < profile["temp_min"] or humidity > profile["humidity_max"]:
        if sensor_id not in sensor_fail_counts:
            sensor_fail_counts[sensor_id] = 0
        sensor_fail_counts[sensor_id] += 1
        
        if sensor_fail_counts[sensor_id] >= MAX_FAILURES_ALLOWED:
            is_breach = True
            # --- 5. SEND PUSH NOTIFICATION ---
            # We only send the alert once (when the count EXACTLY hits the limit)
            if sensor_fail_counts[sensor_id] == MAX_FAILURES_ALLOWED:
                excess = temp - profile["temp_max"]
                send_alert(reading, excess, profile)
                
                # --- 6. STORE BREACH EVENT SEPARATELY ---
                if write_api:
                    try:
                        breach_point = Point("breach_event") \
                            .tag("sensor_id", reading["sensor_id"]) \
                            .tag("shipment_id", reading["shipment_id"]) \
                            .field("temperature_c", reading["temperature_c"]) \
                            .field("breach_magnitude", excess) \
                            .field("location_tag", reading["location_tag"])
                        # We use the INFLUX_BUCKET variable from our config
                        write_api.write(bucket=INFLUX_BUCKET, record=breach_point)
                        print(f"[{sensor_id}] !!! BREACH EVENT RECORDED !!!")
                    except Exception as e:
                        print(f"Failed to record breach event: {e}")
    else:
        sensor_fail_counts[sensor_id] = 0

    # --- 4. PREPARE FINAL DATA DATA ---
    # Add our calculated metrics to the reading before sending it
    reading["rolling_mean"] = round(float(rolling_mean), 2)
    reading["rolling_std"] = round(float(rolling_std), 2)
    reading["rate_of_change"] = round(float(rate_of_change), 2)
    reading["health_score"] = health_score
    reading["is_breach"] = is_breach

    # --- 5. BROADCAST TO DASHBOARD ---
    try:
        # We send a "POST" request to our API
        # The API will then send it to all WebSocket clients
        requests.post(API_URL, json=reading, timeout=1)
    except Exception as e:
        # If the API isn't running, we just ignore the error
        pass

    # --- 6. STORE TO INFLUXDB ---
    if write_api:
        try:
            point = Point("sensor_reading") \
                .tag("sensor_id", sensor_id) \
                .tag("shipment_id", reading["shipment_id"]) \
                .tag("location", reading["location_tag"]) \
                .tag("product_type", profile_key) \
                .field("temperature_c", float(temp)) \
                .field("humidity_pct", float(humidity)) \
                .field("battery_pct", float(reading["battery_pct"])) \
                .field("is_breach", bool(is_breach)) \
                .field("rolling_mean", reading["rolling_mean"]) \
                .field("rolling_std", reading["rolling_std"]) \
                .field("rate_of_change", reading["rate_of_change"]) \
                .field("health_score", reading["health_score"])
            # Let InfluxDB auto-assign the server timestamp (most reliable)
            write_api.write(bucket=INFLUX_BUCKET, record=point)
            print(f"[{sensor_id}] Data synchronized with Dashboard and InfluxDB.")
        except Exception as e:
            print(f"Failed to save to InfluxDB: {e}")
            traceback.print_exc()

# --- MQTT SETUP ---
mqtt_client = mqtt.Client()
mqtt_client.on_message = on_message

mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
mqtt_client.subscribe(MQTT_TOPIC)
print("Waiting for data...")

try:
    mqtt_client.loop_forever()
except KeyboardInterrupt:
    print("\nSubscriber stopped.")
    mqtt_client.disconnect()
    if influx_client:
        influx_client.close()
