import time
import json
import random
from datetime import datetime
import paho.mqtt.client as mqtt

# --- GLOBAL CONFIGURATION ---
BROKER = "localhost"
PORT = 1883
TOPIC_PREFIX = "cold_chain"
INTERVAL = 5 # seconds between readings

def run_sensor(sensor_config):
    """
    Simulates a single sensor sending data to MQTT.
    sensor_config: dict with keys 'id', 'shipment', 'profile'
    """
    sensor_id = sensor_config.get("id", "UNKNOWN-SENSOR")
    shipment_id = sensor_config.get("shipment", "UNKNOWN-SHIP")
    product_type = sensor_config.get("profile", "standard_vaccines")
    location = sensor_config.get("location", "Truck-101")

    # Initial data
    current_temp = 4.0
    current_humidity = 50.0
    battery_pct = 100.0

    # Connect to the MQTT Broker
    client = mqtt.Client() 
    print(f"[{sensor_id}] Connecting to broker...")
    try:
        client.connect(BROKER, PORT)
        print(f"[{sensor_id}] Connected to {BROKER} successfully!")
    except Exception as e:
        print(f"[{sensor_id}] Failed to connect to broker: {e}")
        return

    print(f"[{sensor_id}] Starting simulation for {shipment_id}. Press Ctrl+C to stop.")

    try:
        while True:
            # 1. CREATE DRIFT
            drift = random.uniform(-0.05, 0.05)
            current_temp = current_temp + drift
            
            # 2. RANDOM SPIKES
            if random.random() < 0.05:
                spike = random.uniform(3, 8)
                current_temp = current_temp + spike
                print(f"[{sensor_id}] !!! WARNING: Temperature spike detected !!!")
            
            # 3. HUMIDITY CHANGE
            current_humidity = current_humidity + random.uniform(-0.5, 0.5)
            
            # 4. BATTERY DRAIN
            battery_pct = battery_pct - 0.05
            if battery_pct < 0:
                battery_pct = 0
                
            # 5. PREPARE THE DATA
            reading = {
                "sensor_id": sensor_id,
                "shipment_id": shipment_id,
                "product_type": product_type,
                "timestamp": datetime.now().isoformat(),
                "temperature_c": round(current_temp, 2),
                "humidity_pct": round(current_humidity, 2),
                "location_tag": location,
                "battery_pct": round(battery_pct, 2)
            }
            
            # 6. SEND THE DATA
            json_payload = json.dumps(reading)
            topic = f"{TOPIC_PREFIX}/{sensor_id}/readings"
            
            client.publish(topic, json_payload)
            print(f"[{sensor_id}] Sent reading to {topic}: {json_payload}")
            
            # 7. WAIT
            time.sleep(INTERVAL)

    except (KeyboardInterrupt, SystemExit):
        print(f"[{sensor_id}] Simulation stopped.")
    finally:
        client.disconnect()

if __name__ == "__main__":
    # Default behavior for single sensor if run directly
    config = {
        "id": "SENSOR-001",
        "shipment": "SHIP-99",
        "profile": "standard_vaccines"
    }
    run_sensor(config)

