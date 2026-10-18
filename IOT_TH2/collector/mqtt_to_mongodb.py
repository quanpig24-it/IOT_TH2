import json
import math
import os
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST", "test.mosquitto.org")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "iot-lab2/CHANGE_TO_RANDOM_ID/telemetry")
CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "iotlab2-python-collector")

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE = os.getenv("MONGODB_DATABASE", "iot_lab2")
RAW_COLLECTION = os.getenv("MONGODB_RAW_COLLECTION", "sensor_raw")

NUMERIC_FIELDS = {
    "temperature", "humidity", "distance_cm",
    "rssi", "sequence", "uptime_s", "timestamp_ms"
}
REQUIRED_FIELDS = {"temperature", "humidity", "distance_cm", "sequence", "uptime_s"}

mongo = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
try:
    mongo.admin.command("ping")
except Exception as exc:
    raise SystemExit(f"Không kết nối được MongoDB ({MONGODB_URI}): {exc}")
db = mongo[DATABASE]
raw_collection = db[RAW_COLLECTION]

def valid_payload(data):
    if not isinstance(data, dict):
        return False, "JSON root phải là object"
    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        return False, f"Thiếu khóa: {sorted(missing)}"
    try:
        values = {}
        for key in REQUIRED_FIELDS:
            values[key] = float(data[key])
            if not math.isfinite(values[key]):
                return False, f"{key} không hữu hạn"
        if not -40 <= values["temperature"] <= 80:
            return False, "temperature ngoài miền hợp lý"
        if not 0 <= values["humidity"] <= 100:
            return False, "humidity ngoài miền 0..100"
        if not 0 <= values["distance_cm"] <= 450:
            return False, "distance_cm ngoài miền 0..450"
    except (TypeError, ValueError):
        return False, "Trường số không hợp lệ"
    return True, "OK"

def on_connect(client, userdata, flags, reason_code, properties):
    print(f"MQTT connected: {reason_code}")
    client.subscribe(MQTT_TOPIC, qos=0)
    print(f"Subscribed: {MQTT_TOPIC}")

def on_message(client, userdata, msg):
    received_at = datetime.now(timezone.utc)
    try:
        data = json.loads(msg.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"[REJECT] JSON lỗi: {exc}")
        return

    ok, reason = valid_payload(data)
    if not ok:
        print(f"[REJECT] {reason}: {data}")
        return

    document = {
        "timestamp": received_at,
        "metadata": {
            "device": "esp32-wokwi",
            "topic": msg.topic
        },
        "payload_valid": True,
        "payload_size_bytes": len(msg.payload),
        "received_at": received_at,
    }
    for key in NUMERIC_FIELDS:
        if key in data:
            try:
                value = float(data[key])
                if math.isfinite(value):
                    document[key] = value
            except (TypeError, ValueError):
                pass

    try:
        raw_collection.insert_one(document)
        timestamp_ms = int(data.get("timestamp_ms", 0) or 0)
        if timestamp_ms > 0:
            latency_ms = received_at.timestamp() * 1000 - timestamp_ms
            print(
                f"[SAVED] seq={data.get('sequence')} "
                f"T={data.get('temperature')}C H={data.get('humidity')}% "
                f"D={data.get('distance_cm')}cm latency≈{latency_ms:.1f}ms"
            )
        else:
            print(f"[SAVED] seq={data.get('sequence')} (chưa có timestamp NTP)")
    except Exception as exc:
        print(f"[ERROR] Không ghi được MongoDB: {exc}")

def main():
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
        protocol=mqtt.MQTTv311,
    )
    client.on_connect = on_connect
    client.on_message = on_message
    print(f"Connecting to MQTT {MQTT_HOST}:{MQTT_PORT} ...")
    print(f"MongoDB: {MONGODB_URI} / {DATABASE}.{RAW_COLLECTION}")
    try:
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("Stopping collector...")
    finally:
        client.disconnect()
        mongo.close()

if __name__ == "__main__":
    main()
