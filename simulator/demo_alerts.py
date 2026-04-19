import json
import time
import paho.mqtt.client as mqtt
from datetime import datetime

# Settings
MQTT_BROKER = "127.0.0.1"
TOPIC = "cold_chain/DEMO-SENSOR/readings"

def trigger_demo_breach():
    client = mqtt.Client()
    client.connect(MQTT_BROKER, 1883)
    
    print("🚀 Starting Demonstration Breach...")
    
    # We will send 3 readings that are way above the 8°C limit for vaccines
    high_temps = [12.5, 14.2, 15.8]
    
    for i, temp in enumerate(high_temps):
        data = {
            "sensor_id": "DEMO-SENSOR",
            "shipment_id": "DEMO-PHASE-1",
            "product_type": "standard_vaccines",
            "timestamp": datetime.now().isoformat(),
            "temperature_c": temp,
            "humidity_pct": 55.0,
            "battery_pct": 88.0
        }
        
        client.publish(TOPIC, json.dumps(data))
        print(f"[{i+1}/3] Sent High Temp: {temp}°C")
        
        # Wait 2 seconds between each so the dashboard can refresh
        time.sleep(2)
    
    print("\n✅ Demo Complete! Check your Dashboard and Ntfy.sh notification.")
    client.disconnect()

if __name__ == "__main__":
    trigger_demo_breach()
