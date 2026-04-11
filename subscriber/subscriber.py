import json
import paho.mqtt.client as mqtt
import os
import pandas as pd
from collections import deque
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# Load the .env file to get our secret tokens
load_dotenv()

# --- CONFIGURATION ---
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "cold_chain/#"

# InfluxDB Settings (Reading from .env)
INFLUX_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUX_ORG = os.getenv("INFLUXDB_ORG")
INFLUX_BUCKET = os.getenv("INFLUXDB_BUCKET")

# --- ALERT & HISTORY SETTINGS ---
MAX_FAILURES_ALLOWED = 3
sensor_fail_counts = {}

# We keep the last 12 readings for each sensor to calculate averages
# A 'deque' is a special list that automatically removes the oldest item when it gets full
HISTORY_SIZE = 12
sensor_history = {}

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

# --- MESSAGE HANDLER ---
def on_message(client, userdata, message):
    payload = message.payload.decode()
    reading = json.loads(payload)
    
    sensor_id = reading["sensor_id"]
    temp = reading["temperature_c"]
    humidity = reading["humidity_pct"]
    
    # --- 1. TRACK HISTORY FOR PANDAS ---
    if sensor_id not in sensor_history:
        # Create a new deque for this sensor if we haven't seen it before
        sensor_history[sensor_id] = deque(maxlen=HISTORY_SIZE)
    
    # Add the current temperature to our history
    sensor_history[sensor_id].append(temp)
    
    # --- 2. CALCULATE ROLLING METRICS (Using Pandas) ---
    # We turn our history list into a Pandas DataFrame (like a table)
    history_list = list(sensor_history[sensor_id])
    df = pd.DataFrame(history_list, columns=["temp"])
    
    rolling_mean = 0.0
    rolling_std = 0.0
    rate_of_change = 0.0
    
    # We can only calculate these if we have enough data
    if len(history_list) >= 2:
        # 'diff' shows the change from the last reading
        rate_of_change = df["temp"].diff().iloc[-1]
        
    if len(history_list) == HISTORY_SIZE:
        # Calculate the average and standard deviation of the last 12 readings
        rolling_mean = df["temp"].mean()
        rolling_std = df["temp"].std()
    
    # --- 3. CHECK THRESHOLDS ---
    profile = PROFILES["standard_vaccines"]
    is_breach = False
    
    if temp > profile["temp_max"] or temp < profile["temp_min"] or humidity > profile["humidity_max"]:
        is_breach = True
        if sensor_id not in sensor_fail_counts:
            sensor_fail_counts[sensor_id] = 0
        sensor_fail_counts[sensor_id] += 1
    else:
        sensor_fail_counts[sensor_id] = 0

    # --- 4. STORE TO INFLUXDB (Including our new Pandas metrics) ---
    if write_api:
        try:
            point = Point("sensor_reading") \
                .tag("sensor_id", sensor_id) \
                .tag("shipment_id", reading["shipment_id"]) \
                .field("temperature_c", float(temp)) \
                .field("humidity_pct", float(humidity)) \
                .field("battery_pct", float(reading["battery_pct"])) \
                .field("is_breach", bool(is_breach)) \
                .field("rolling_mean", float(rolling_mean)) \
                .field("rolling_std", float(rolling_std)) \
                .field("rate_of_change", float(rate_of_change)) \
                .time(reading["timestamp"])
            
            write_api.write(bucket=INFLUX_BUCKET, record=point)
            print(f"[{sensor_id}] Temp: {temp}C | Avg(12): {round(rolling_mean, 2)}C | Delta: {round(rate_of_change, 2)}C")
        except Exception as e:
            print(f"Failed to save to InfluxDB: {e}")

# --- MQTT SETUP ---
mqtt_client = mqtt.Client()
mqtt_client.on_message = on_message

mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
mqtt_client.subscribe(MQTT_TOPIC)
print("Waiting for data and computing rolling metrics...")

try:
    mqtt_client.loop_forever()
except KeyboardInterrupt:
    print("\nSubscriber stopped.")
    mqtt_client.disconnect()
    if influx_client:
        influx_client.close()
