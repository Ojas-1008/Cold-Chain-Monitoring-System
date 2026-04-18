from dotenv import load_dotenv
import os
from influxdb_client import InfluxDBClient

load_dotenv()

url = os.getenv("INFLUXDB_URL", "http://127.0.0.1:8086").replace("localhost", "127.0.0.1")
token = os.getenv("INFLUXDB_TOKEN")
org = os.getenv("INFLUXDB_ORG")
bucket = os.getenv("INFLUXDB_BUCKET")

client = InfluxDBClient(url=url, token=token, org=org)
query_api = client.query_api()

# Query absolutely everything in the bucket in the last 24 hours
query = f'''
from(bucket: "{bucket}")
  |> range(start: -24h)
'''

print("=== ALL DATA IN BUCKET LAST 24H ===")
result = query_api.query(query)
tables = list(result)
count = 0
for table in tables:
    for record in table.records:
        count += 1
        if count <= 10:
            print(f"  sensor_id={record.values.get('sensor_id','N/A')} | field={record.get_field()} | val={record.get_value()} | time={record.get_time()}")

print(f"\nTotal records: {count}")
client.close()
