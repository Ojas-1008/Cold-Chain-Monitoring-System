import time
import json
import random
import uuid
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
from faker import Faker

class ColdChainSimulator:
    def __init__(self, broker="localhost", port=1883):
        self.broker = broker
        self.port = port
        self.fake = Faker()
        
        # Simulation parameters
        self.sensor_id = f"SENSOR-{uuid.uuid4().hex[:8].upper()}"
        self.topic = f"cold_chain/{self.sensor_id}/readings"
        self.shipment_id = f"SHIP-{uuid.uuid4().hex[:6].upper()}"
        self.location_tag = random.choice(["Warehouse-A", "Truck-101", "Distribution-Center-North", "Port-Exit"])
        
        # Initial states
        self.current_temp = random.uniform(2.0, 5.0)
        self.current_humidity = random.uniform(40.0, 60.0)
        self.battery_pct = 100.0
        
        # Drift and Spikes
        self.spike_probability = 0.05  # 5% chance of a spike
        self.drift_range = (-0.05, 0.05)
        
        # MQTT Client
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def connect(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            print(f"Connected to MQTT Broker: {self.broker}:{self.port}")
        except Exception as e:
            print(f"Connection failed: {e}")

    def generate_reading(self):
        # 1. Apply gradual drift
        self.current_temp += random.uniform(*self.drift_range)
        self.current_humidity += random.uniform(-0.5, 0.5)
        
        # 2. Random spikes
        if random.random() < self.spike_probability:
            spike_val = random.uniform(3.0, 8.0)
            self.current_temp += spike_val
            print(f"!!! SPIKE DETECTED: +{spike_val:.2f}C !!!")
        
        # 3. Battery drain
        self.battery_pct -= random.uniform(0.01, 0.1)
        self.battery_pct = max(0, self.battery_pct)
        
        # 4. Build message
        reading = {
            "sensor_id": self.sensor_id,
            "shipment_id": self.shipment_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "temperature_c": round(self.current_temp, 2),
            "humidity_pct": round(self.current_humidity, 2),
            "location_tag": self.location_tag,
            "battery_pct": round(self.battery_pct, 2)
        }
        return reading

    def run(self, interval=5):
        self.connect()
        print(f"Starting simulation for {self.sensor_id}...")
        try:
            while True:
                data = self.generate_reading()
                payload = json.dumps(data)
                
                # Publish to MQTT
                result = self.client.publish(self.topic, payload)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    print(f"Published: {payload}")
                else:
                    print(f"Failed to publish message to topic {self.topic}")
                
                time.sleep(interval)
        except KeyboardInterrupt:
            print("Simulation stopped.")
            self.client.disconnect()

if __name__ == "__main__":
    sim = ColdChainSimulator()
    sim.run()
