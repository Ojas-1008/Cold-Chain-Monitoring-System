import time
import json
import random
from datetime import datetime
import paho.mqtt.client as mqtt

# -- SETTINGS --
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
TOPIC_BASE = "cold_chain"

def run_sensor(config):
    # Get sensor info from the config dictionary
    name = config.get("id", "S-000")
    shipment = config.get("shipment", "Unknown")
    product = config.get("profile", "vaccines")
    
    # Starting values for the simulation
    temp = 4.0
    humidity = 50.0
    battery = 100.0

    # Create an MQTT client to send data
    client = mqtt.Client()
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT)
        print(f"[{name}] Connected to Broker.")
    except:
        print(f"[{name}] Connect failed! Is Mosquitto running?")
        return

    # THE MAIN LOOP: Runs until you stop the script
    try:
        while True:
            # 1. Simulating small temperature changes
            temp = temp + random.uniform(-0.1, 0.1)
            
            # 2. Random temperature spikes (malfunctions)
            # This simulates a cooling unit failure (hot) or a thermostat bug (cold)
            if random.random() < 0.05:
                # 70% chance of a "Hot Spike", 30% chance of a "Cold Spike"
                if random.random() < 0.7:
                    temp = temp + random.uniform(2, 5)
                    print(f"[{name}] Alert: High Temp Spike!")
                else:
                    temp = temp - random.uniform(2, 5)
                    print(f"[{name}] Alert: Low Temp Drop!")

            # 3. Battery drain
            battery = battery - 0.1
            if battery < 0: battery = 0
            
            # 4. Prepare the message
            data = {
                "sensor_id": name,
                "shipment_id": shipment,
                "product_type": product,
                "timestamp": datetime.now().isoformat(),
                "temperature_c": round(temp, 2),
                "humidity_pct": round(humidity, 2),
                "battery_pct": round(battery, 2)
            }
            
            # 5. Convert to JSON and send it
            json_string = json.dumps(data)
            topic = f"{TOPIC_BASE}/{name}/readings"
            
            client.publish(topic, json_string)
            print(f"[{name}] Sent: {json_string}")
            
            # 6. Wait before sending the next one
            time.sleep(5)

    except KeyboardInterrupt:
        print(f"[{name}] Stopping...")
        client.disconnect()

# If this file is run by itself (not by multi_sensor_sim)
if __name__ == "__main__":
    test_config = {"id": "TEST-1", "shipment": "SHP-1", "profile": "vaccines"}
    run_sensor(test_config)

