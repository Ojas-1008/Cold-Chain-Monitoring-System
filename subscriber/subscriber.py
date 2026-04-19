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
last_temperatures = {} # NEW: Stores ONLY the last temperature for trend analysis
last_battery = {}      # NEW: Stores ONLY the last battery pct for trend analysis

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
    temp = reading["temperature_c"]
    status = "too hot" if temp > profile["temp_max"] else "too cold"
    
    msg = f"ALERT: {reading['sensor_id']} is {status}! Current: {temp}C"
    try:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode("utf-8"))
        print(f"Push notification sent: {msg}")
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

    # -- Step 4.5: Time to Breach Prediction (Improved Algorithm) --
    # "How many minutes until we hit the Danger Zone?"
    # IMPROVEMENT: Instead of just the last 2 points, we look at the trend over the last 5 readings.
    # This is "Smoothing"—it prevents the prediction from jumping wildly due to minor jitters.
    minutes_to_breach = -1
    
    if len(history) >= 5:
        # Calculate the absolute change over the last 5 readings (covering ~25 seconds)
        recent_delta = history[-1] - history[-5]
        
        # The 'slope' per reading (5 seconds)
        # We divide by 4 because there are 4 intervals between 5 points
        avg_slope_per_reading = recent_delta / 4
        
        # Check for predictive breaches if we haven't breached yet
        if not is_breach:
            if avg_slope_per_reading > 0: # Trending HOT
                degrees_to_go = rules["temp_max"] - temp
                minutes_to_breach = degrees_to_go / (avg_slope_per_reading * 12)
            elif avg_slope_per_reading < 0: # Trending COLD
                degrees_to_go = temp - rules["temp_min"]
                minutes_to_breach = degrees_to_go / (abs(avg_slope_per_reading) * 12)

            # DATA SCIENCE TIP: We add a 10% "Safety Margin" to be conservative.
            # It's better to warn the driver early than late.
            if minutes_to_breach != -1:
                minutes_to_breach = round(minutes_to_breach * 0.9, 1)

    # -- Step 4.6: battery Life Prediction (NEW) --
    # "How many HOURS until the sensor runs out of power?"
    hours_until_dead = -1 # A value of -1 means "Not enough data yet"
    
    if s_id in last_battery:
        prev_batt = last_battery[s_id]
        # Calculate how much it dropped since 5 seconds ago
        drop_rate = prev_batt - battery 
        
        # We only care if it's actually dropping
        if drop_rate > 0:
            # 12 readings-per-minute * 60 minutes = 720 readings per hour
            readings_per_hour = 720
            hours_until_dead = battery / (drop_rate * readings_per_hour)
            hours_until_dead = round(hours_until_dead, 1)

    # Save the current values for the NEXT prediction
    last_temperatures[s_id] = temp
    last_battery[s_id] = battery

    # -- Step 5: Update reading with new info --
    reading["rolling_mean"] = round(avg_temp, 2)
    reading["health_score"] = health
    reading["is_breach"] = is_breach
    reading["minutes_to_breach"] = minutes_to_breach 
    reading["hours_until_dead"] = hours_until_dead

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
            .tag("product_type", p_type) \
            .field("temperature_c", float(temp)) \
            .field("battery_pct", float(battery)) \
            .field("is_breach", bool(is_breach)) \
            .field("health_score", float(health)) \
            .field("minutes_to_breach", float(minutes_to_breach)) \
            .field("hours_until_dead", float(hours_until_dead))
        
        writer.write(bucket=BUCKET, record=p)

# 4. START THE SUBSCRIBER
# We use CallbackAPIVersion.VERSION2 to avoid deprecation warnings
subscriber = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
subscriber.on_message = process_message

try:
    subscriber.connect(BROKER, 1883)
    subscriber.subscribe(TOPIC)
    print("Subscriber is listening for sensor data...")
    subscriber.loop_forever()
except KeyboardInterrupt:
    print("Stopped.")
    subscriber.disconnect()
