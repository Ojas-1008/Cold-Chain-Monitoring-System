import threading
import time
from sensor_sim import run_sensor

def main():
    sensors = [
        {"id": "SENSOR-001", "shipment": "SHP-A", "profile": "standard_vaccines"},
        {"id": "SENSOR-002", "shipment": "SHP-B", "profile": "fresh_produce"},
        {"id": "SENSOR-003", "shipment": "SHP-C", "profile": "frozen_meat"},
        {"id": "SENSOR-004", "shipment": "SHP-D", "profile": "pharmaceuticals"},
        {"id": "SENSOR-005", "shipment": "SHP-E", "profile": "standard_vaccines"},
    ]

    print(f"Launching {len(sensors)} sensors...")

    threads = []
    for sensor in sensors:
        t = threading.Thread(target=run_sensor, args=(sensor,))
        t.daemon = True  # Stops with the main script
        t.start()
        threads.append(t)
        time.sleep(0.5) # Brief delay between starts

    print("All sensors launched. Press Ctrl+C to stop all simulations.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping all sensors...")

if __name__ == "__main__":
    main()
