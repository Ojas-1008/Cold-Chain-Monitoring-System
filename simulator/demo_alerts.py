import json
import time
import sys
import paho.mqtt.client as mqtt
from datetime import datetime

# Settings
MQTT_BROKER = "127.0.0.1"
TOPIC = "cold_chain/DEMO-SENSOR/readings"

def send_readings(temps, label):
    """Utility to send a sequence of readings to trigger a breach"""
    # Use VERSION2 to avoid deprecation warnings
    # Note: If paho-mqtt version < 2.0, this might fail, but recent installation is likely 2.0+
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except:
        client = mqtt.Client() # Fallback for older versions
        
    try:
        client.connect(MQTT_BROKER, 1883)
    except Exception as e:
        print(f"❌ Error: Could not connect to MQTT broker at {MQTT_BROKER}. Is it running?")
        return

    print(f"\n🚀 Starting {label} Breach Demo (3 readings for MAX_FAILURES threshold)...")
    
    for i, temp in enumerate(temps):
        data = {
            "sensor_id": "DEMO-SENSOR",
            "shipment_id": "DEMO-LIVE-TEST",
            "product_type": "standard_vaccines", # Range: 2.0°C to 8.0°C
            "timestamp": datetime.now().isoformat(),
            "temperature_c": temp,
            "humidity_pct": 55.0,
            "battery_pct": 88.0
        }
        
        client.publish(TOPIC, json.dumps(data))
        print(f"  [{i+1}/3] Sent Temp: {temp}°C")
        
        # Wait 2 seconds between each reading
        time.sleep(2)
    
    client.disconnect()

if __name__ == "__main__":
    print("="*40)
    print("   COLD CHAIN NOTIFICATION TESTER")
    print("="*40)
    print("Options:")
    print("  1. Test HOT Breach  (Temp > 8.0°C)")
    print("  2. Test COLD Breach (Temp < 2.0°C)")
    print("  3. Test BOTH Sequences")
    print("="*40)
    
    choice = input("Enter choice (1, 2, or 3): ").strip()
    
    if choice == "1" or choice == "3":
        # Readings for standard_vaccines (Max limit: 8.0°C)
        send_readings([10.5, 12.2, 14.8], "Hot Temp")
        
    if choice == "3":
        print("\n⏳ Cooling down for 5 seconds...")
        time.sleep(5)
        
    if choice == "2" or choice == "3":
        # Readings for standard_vaccines (Min limit: 2.0°C)
        send_readings([1.5, 0.8, -1.2], "Cold Temp")
        
    print("\n✅ Verification complete! Check ntfy.sh and the Dashboard.")
