import json
import os
import requests
import paho.mqtt.client as mqtt
from datetime import datetime
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# 1. SETUP & CONFIG
load_dotenv()

# Connection details
BROKER = "127.0.0.1"
TOPIC = "cold_chain/#"
API_URL = "http://127.0.0.1:8000/broadcast"

# Database details
INFLUX_URL = os.getenv("INFLUXDB_URL", "http://127.0.0.1:8086")
TOKEN = os.getenv("INFLUXDB_TOKEN")
ORG = os.getenv("INFLUXDB_ORG")
BUCKET = os.getenv("INFLUXDB_BUCKET")

# Alerts settings
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "cold-chain-alerts")
MAX_FAILURES = 3

# Memory for sensors
sensor_fail_counts = {}
sensor_history = {} # Stores last 12 temperatures

# Load product rules (min/max temps)
with open("config/profiles.json", "r") as f:
    PROFILES = json.load(f)

# Connect to InfluxDB
try:
    influx = InfluxDBClient(url=INFLUX_URL, token=TOKEN, org=ORG)
    writer = influx.write_api(write_options=SYNCHRONOUS)
    print("Database connected!")
except:
    print("Database connection failed!")
    writer = None

# 2. HELPER FUNCTIONS

def send_push_notification(reading, profile):
    """Sends an alert to the phone via ntfy.sh"""
    msg = f"ALERT: {reading['sensor_id']} is too hot! Current: {reading['temperature_c']}C"
    try:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode("utf-8"))
        print("Push notification sent!")
    except:
        print("Failed to send notification.")

# 3. MESSAGE PROCESSING

def process_message(client, userdata, message):
    # Get the data from the sensor
    raw_data = message.payload.decode()
    reading = json.loads(raw_data)
    
    s_id = reading["sensor_id"]
    temp = reading["temperature_c"]
    
    # -- Step 1: Track history for averages --
    if s_id not in sensor_history:
        sensor_history[s_id] = []
    
    sensor_history[s_id].append(temp)
    # Keep only the last 12 readings
    if len(sensor_history[s_id]) > 12:
        sensor_history[s_id].pop(0)
    
    # -- Step 2: Calculate basic average --
    history = sensor_history[s_id]
    avg_temp = sum(history) / len(history)

    # -- Step 3: Check for breaches (Is it too hot/cold?) --
    p_type = reading.get("product_type", "vaccines")
    rules = PROFILES.get(p_type, PROFILES["standard_vaccines"])
    
    is_breach = False
    # Check if outside limits
    if temp > rules["temp_max"] or temp < rules["temp_min"]:
        current_fails = sensor_fail_counts.get(s_id, 0) + 1
        sensor_fail_counts[s_id] = current_fails
        
        # If it fails 3 times in a row, it's a real breach
        if current_fails >= MAX_FAILURES:
            is_breach = True
            if current_fails == MAX_FAILURES:
                send_push_notification(reading, rules)
    else:
        # Reset counter if back to normal
        sensor_fail_counts[s_id] = 0

    # -- Step 4: Calculate Health Score --
    # Simple score based on battery and stability
    battery = reading.get("battery_pct", 100)
    health = (battery * 0.8) + (20 if not is_breach else 0)
    health = round(health / 100, 2)

    # -- Step 5: Update reading with new info --
    reading["rolling_mean"] = round(avg_temp, 2)
    reading["health_score"] = health
    reading["is_breach"] = is_breach

    # -- Step 6: Send to Dashboard API --
    try:
        requests.post(API_URL, json=reading, timeout=1)
    except:
        pass # Dashboard might be closed

    # -- Step 7: Save to Database --
    if writer:
        p = Point("sensor_reading") \
            .tag("sensor_id", s_id) \
            .tag("shipment_id", reading["shipment_id"]) \
            .field("temperature_c", float(temp)) \
            .field("is_breach", bool(is_breach)) \
            .field("health_score", float(health))
        
        writer.write(bucket=BUCKET, record=p)

# 4. START THE SUBSCRIBER
subscriber = mqtt.Client()
subscriber.on_message = process_message

try:
    subscriber.connect(BROKER, 1883)
    subscriber.subscribe(TOPIC)
    print("Subscriber is listening for sensor data...")
    subscriber.loop_forever()
except KeyboardInterrupt:
    print("Stopped.")
    subscriber.disconnect()
