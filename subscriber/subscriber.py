import json
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# --- CONFIGURATION (Change these to match your setup) ---
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "cold_chain/#"

# InfluxDB Settings (Placeholders)
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "YOUR_INFLUXDB_TOKEN"
INFLUX_ORG = "YOUR_ORG"
INFLUX_BUCKET = "cold_chain_data"

# --- LOAD THRESHOLDS ---
# We read the profiles.json file once at the beginning
print("Loading product profiles...")
with open("config/profiles.json", "r") as f:
    PROFILES = json.load(f)
print("Profiles loaded successfully!")

# --- SETUP INFLUXDB ---
# This creates a connection to our database
# NOTE: If you haven't set up InfluxDB yet, you can comment this out
try:
    influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = influx_client.write_api(write_options=SYNCHRONOUS)
    print("Connected to InfluxDB!")
except Exception as e:
    print(f"Warning: Could not connect to InfluxDB. Error: {e}")
    write_api = None

# --- MESSAGE HANDLER ---
# This function runs every time a new message arrives on MQTT
def on_message(client, userdata, message):
    # 1. Decode the message
    # The message comes in as "bytes", so we turn it into a string and then a Python dictionary
    payload = message.payload.decode()
    reading = json.loads(payload)
    
    sensor_id = reading["sensor_id"]
    temp = reading["temperature_c"]
    humidity = reading["humidity_pct"]
    
    print(f"\n--- New Reading from {sensor_id} ---")
    print(f"Temp: {temp}C, Humidity: {humidity}%")

    # 2. CHECK THRESHOLDS
    # We'll use 'standard_vaccines' as a default for this example
    # Beginners can later update this to pick a profile based on shipment_id
    profile_name = "standard_vaccines"
    limits = PROFILES[profile_name]
    
    # Check Temperature
    if temp < limits["temp_min"] or temp > limits["temp_max"]:
        print(f"!!! ALERT: Temperature Breach! ({temp}C is outside {limits['temp_min']}-{limits['temp_max']}C)")
    
    # Check Humidity
    if humidity > limits["humidity_max"]:
        print(f"!!! ALERT: Humidity too high! ({humidity}% > {limits['humidity_max']}%)")

    # 3. STORE TO INFLUXDB
    if write_api:
        try:
            # Prepare the data point for InfluxDB
            point = Point("sensor_readings") \
                .tag("sensor_id", sensor_id) \
                .tag("shipment_id", reading["shipment_id"]) \
                .tag("location", reading["location_tag"]) \
                .field("temperature", float(temp)) \
                .field("humidity", float(humidity)) \
                .field("battery", float(reading["battery_pct"]))
            
            # Write to database
            write_api.write(bucket=INFLUX_BUCKET, record=point)
            print("Successfully stored in InfluxDB.")
        except Exception as e:
            print(f"Failed to save to InfluxDB: {e}")

# --- MQTT SETUP ---
# Create the MQTT client and connect
mqtt_client = mqtt.Client()
mqtt_client.on_message = on_message

print(f"Connecting to MQTT Broker at {MQTT_BROKER}...")
mqtt_client.connect(MQTT_BROKER, MQTT_PORT)

# Subscribe to all cold chain topics
mqtt_client.subscribe(MQTT_TOPIC)
print(f"Subscribed to {MQTT_TOPIC}. Waiting for data...")

# This keeps the script running forever
try:
    mqtt_client.loop_forever()
except KeyboardInterrupt:
    print("\nSubscriber stopped.")
    mqtt_client.disconnect()
    if influx_client:
        influx_client.close()
