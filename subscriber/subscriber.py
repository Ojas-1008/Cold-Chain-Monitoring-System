import json
import paho.mqtt.client as mqtt
import os
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

# --- ALERT SETTINGS ---
# This is our "Soft Limit". We only alert if there are 3 bad readings in a row.
MAX_FAILURES_ALLOWED = 3
# This dictionary will keep track of how many bad readings each sensor has had
# Example: {"SENSOR-001": 2, "SENSOR-002": 0}
sensor_fail_counts = {}

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
    
    # Use 'standard_vaccines' as our rulebook for now
    profile = PROFILES["standard_vaccines"]
    
    is_breach = False
    breach_reason = ""
    magnitude = 0.0

    # 1. CHECK TEMPERATURE
    if temp > profile["temp_max"]:
        is_breach = True
        magnitude = temp - profile["temp_max"]
        breach_reason = f"Temperature too high! (Over by {round(magnitude, 2)}C)"
    elif temp < profile["temp_min"]:
        is_breach = True
        magnitude = profile["temp_min"] - temp
        breach_reason = f"Temperature too low! (Under by {round(magnitude, 2)}C)"

    # 2. CHECK HUMIDITY
    if humidity > profile["humidity_max"]:
        is_breach = True
        # We don't overwrite the temp reason if it's already there, just add to it
        breach_reason += f" Humidity too high! ({humidity}% > {profile['humidity_max']}%)"

    # 3. SOFT LIMIT LOGIC (Consecutive bad readings)
    if is_breach:
        # If the sensor isn't in our list yet, start at 0
        if sensor_id not in sensor_fail_counts:
            sensor_fail_counts[sensor_id] = 0
            
        # Add 1 to the fail count
        sensor_fail_counts[sensor_id] += 1
        
        current_fails = sensor_fail_counts[sensor_id]
        print(f"--- ALERT: {sensor_id} is out of range! (Failure {current_fails}/{MAX_FAILURES_ALLOWED}) ---")
        
        # Only fire a REAL alert if we hit the limit
        if current_fails >= MAX_FAILURES_ALLOWED:
            print(f"!!! CRITICAL ALERT: {sensor_id} has exceeded the soft limit !!!")
            print(f"REASON: {breach_reason}")
    else:
        # If the reading is GOOD, reset the counter to zero
        sensor_fail_counts[sensor_id] = 0
        print(f"Reading from {sensor_id}: {temp}C, {humidity}% [OK]")

    # 4. STORE TO INFLUXDB (Even if it's a breach, we want the data)
    if write_api:
        try:
            # We create a "Point" which is like a single row in a spreadsheet
            # Measurement name: "sensor_reading"
            point = Point("sensor_reading") \
                .tag("sensor_id", sensor_id) \
                .tag("shipment_id", reading["shipment_id"]) \
                .tag("location", reading["location_tag"]) \
                .field("temperature_c", float(temp)) \
                .field("humidity_pct", float(humidity)) \
                .field("battery_pct", float(reading["battery_pct"])) \
                .field("is_breach", bool(is_breach)) \
                .time(reading["timestamp"]) # Use the timestamp from the simulator
            
            # Send the point to our InfluxDB bucket
            write_api.write(bucket=INFLUX_BUCKET, record=point)
            print(f"Stored data for {sensor_id} in InfluxDB.")
        except Exception as e:
            print(f"Failed to save to InfluxDB: {e}")

# --- MQTT SETUP ---
mqtt_client = mqtt.Client()
mqtt_client.on_message = on_message

print(f"Connecting to MQTT Broker...")
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
