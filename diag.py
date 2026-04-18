import os
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient

load_dotenv()

# Load settings from environment (.env)
URL = os.getenv("INFLUXDB_URL", "http://127.0.0.1:8086")
TOKEN = os.getenv("INFLUXDB_TOKEN")
ORG = os.getenv("INFLUXDB_ORG")
BUCKET = os.getenv("INFLUXDB_BUCKET")

# Connect to InfluxDB
client = InfluxDBClient(url=URL, token=TOKEN, org=ORG) or exit("Failed to connect!")
query_api = client.query_api()

# Query the last 24 hours of data
query = f'from(bucket: "{BUCKET}") |> range(start: -24h)'
result = query_api.query(query)

print("--- RECENT DATABASE RECORDS ---")
total_count = 0

for table in result:
    for record in table.records:
        total_count += 1
        # Show a preview of the first 10 entries
        if total_count <= 10:
            print(f"[{record.get_time()}] {record.values.get('sensor_id')}: {record.get_field()} = {record.get_value()}")

print(f"\nTotal records found: {total_count}")
client.close()
