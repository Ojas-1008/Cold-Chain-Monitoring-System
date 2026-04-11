import time
import json
import random
from datetime import datetime
import paho.mqtt.client as mqtt

# --- CONFIGURATION (Change these if needed) ---
BROKER = "localhost"
PORT = 1883
TOPIC_PREFIX = "cold_chain"
INTERVAL = 5 # seconds between readings

# --- SENSOR CONSTANTS ---
# Using simple names instead of complex IDs for beginners
SENSOR_ID = "SENSOR-001"
SHIPMENT_ID = "SHIP-99"
LOCATION = "Truck-101"

# --- INITIAL DATA ---
# Starting points for our simulation
current_temp = 4.0
current_humidity = 50.0
battery_pct = 100.0

# Connect to the MQTT Broker
client = mqtt.Client() # Simple client initialization
print("Connecting to broker...")
client.connect(BROKER, PORT)
print(f"Connected to {BROKER} successfully!")

print(f"Starting simulation for {SENSOR_ID}. Press Ctrl+C to stop.")

try:
    while True:
        # 1. CREATE DRIFT (Temperature changes slightly)
        # We add a tiny random number to the current temperature
        drift = random.uniform(-0.05, 0.05)
        current_temp = current_temp + drift
        
        # 2. RANDOM SPIKES (5% chance of a sudden jump)
        if random.random() < 0.05:
            spike = random.uniform(3, 8)
            current_temp = current_temp + spike
            print("!!! WARNING: Temperature spike detected !!!")
        
        # 3. HUMIDITY CHANGE
        current_humidity = current_humidity + random.uniform(-0.5, 0.5)
        
        # 4. BATTERY DRAIN
        battery_pct = battery_pct - 0.05
        if battery_pct < 0:
            battery_pct = 0
            
        # 5. PREPARE THE DATA (The "Reading")
        # We put all our variables into one dictionary (like a box)
        reading = {
            "sensor_id": SENSOR_ID,
            "shipment_id": SHIPMENT_ID,
            "timestamp": datetime.now().isoformat(), # Current time as text
            "temperature_c": round(current_temp, 2), # Round to 2 decimals
            "humidity_pct": round(current_humidity, 2),
            "location_tag": LOCATION,
            "battery_pct": round(battery_pct, 2)
        }
        
        # 6. SEND THE DATA (Publish)
        # Convert the dictionary to a JSON string first
        json_payload = json.dumps(reading)
        topic = f"{TOPIC_PREFIX}/{SENSOR_ID}/readings"
        
        client.publish(topic, json_payload)
        print(f"Sent reading to {topic}: {json_payload}")
        
        # 7. WAIT
        time.sleep(INTERVAL)

except KeyboardInterrupt:
    print("\nSimulation stopped by user.")
    client.disconnect()
