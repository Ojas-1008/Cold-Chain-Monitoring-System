import threading
import time
from sensor_sim import run_sensor

# List of sensors to simulate
sensor_list = [
    {"id": "SENSOR-001", "shipment": "SHP-ALPHA", "profile": "vaccines"},
    {"id": "SENSOR-002", "shipment": "SHP-BETA", "profile": "food"},
    {"id": "SENSOR-003", "shipment": "SHP-GAMMA", "profile": "meat"},
    {"id": "SENSOR-004", "shipment": "SHP-DELTA", "profile": "medicine"},
]

print("Starting Fleet Simulation...")

# Start a new thread for each sensor in the list
for config in sensor_list:
    # We use threading so they all run at the same time
    thread = threading.Thread(target=run_sensor, args=(config,))
    thread.daemon = True # This ensures they stop when the main script stops
    thread.start()
    print(f"Started {config['id']}")
    time.sleep(1) # Wait a second before starting the next one

print("\nAll sensors are running!")
print("Press Ctrl+C to stop the simulation.\n")

# Keep the script running forever (or until Ctrl+C)
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nShutting down sensors...")
