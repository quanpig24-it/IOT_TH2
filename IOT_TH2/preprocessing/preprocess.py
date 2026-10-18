import os
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE = os.getenv("MONGODB_DATABASE", "iot_lab2")
RAW_COLLECTION = os.getenv("MONGODB_RAW_COLLECTION", "sensor_raw")
PROCESSED_COLLECTION = os.getenv("MONGODB_PROCESSED_COLLECTION", "sensor_processed")

mongo = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
try:
    mongo.admin.command("ping")
except Exception as exc:
    raise SystemExit(f"Không kết nối được MongoDB: {exc}")

db = mongo[DATABASE]
cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
docs = list(db[RAW_COLLECTION].find(
    {"timestamp": {"$gte": cutoff}},
    {"_id": 0, "timestamp": 1, "metadata": 1, "temperature": 1,
     "humidity": 1, "distance_cm": 1, "rssi": 1, "sequence": 1,
     "uptime_s": 1, "timestamp_ms": 1}
).sort("timestamp", 1))

if not docs:
    mongo.close()
    raise SystemExit("Chưa có dữ liệu trong 24 giờ qua. Hãy chạy firmware và collector trước.")

df = pd.DataFrame(docs)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df["device"] = df["metadata"].apply(lambda x: x.get("device", "unknown") if isinstance(x, dict) else "unknown")
df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp", "device"], keep="last")
metrics = ["temperature", "humidity", "distance_cm"]
for col in metrics:
    if col not in df.columns:
        df[col] = np.nan
    df[col] = pd.to_numeric(df[col], errors="coerce")

# Làm sạch bản ghi thiếu giá trị đo chính.
df = df.dropna(subset=metrics).copy()

# Loại ngoại lai bằng IQR; đánh dấu NaN trước khi nội suy.
for col in metrics:
    q1, q3 = df[col].quantile([0.25, 0.75])
    iqr = q3 - q1
    if pd.notna(iqr) and iqr > 0:
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        df.loc[(df[col] < lower) | (df[col] > upper), col] = np.nan

df = df.set_index("timestamp").sort_index()
df[metrics] = df[metrics].interpolate(method="time", limit=2).ffill(limit=1).bfill(limit=1)

# Resampling 10 giây: lấy giá trị trung bình mỗi cửa sổ.
sampled = df[metrics].resample("10s").mean().dropna(how="all")
if sampled.empty:
    mongo.close()
    raise SystemExit("Không đủ dữ liệu hợp lệ để resample.")

for col in metrics:
    sampled[f"{col}_rolling_mean"] = sampled[col].rolling(window=3, min_periods=1).mean()
    sampled[f"{col}_delta"] = sampled[col].diff().fillna(0)

for col in metrics:
    min_v, max_v = sampled[col].min(), sampled[col].max()
    sampled[f"{col}_normalized"] = 0.0 if max_v == min_v else (sampled[col] - min_v) / (max_v - min_v)

out = []
for timestamp, row in sampled.iterrows():
    doc = {
        "timestamp": timestamp.to_pydatetime(),
        "metadata": {"device": "esp32-wokwi"},
        "processing": {
            "method": "IQR+time_interpolation+resample_10s+rolling3+delta+minmax",
            "processed_at": datetime.now(timezone.utc),
        },
    }
    for col, value in row.items():
        if pd.notna(value) and np.isfinite(float(value)):
            doc[col] = float(value)
    out.append(doc)

if out:
    # Upsert theo timestamp/device để chạy lại script không tạo bản sao.
    collection = db[PROCESSED_COLLECTION]
    for doc in out:
        collection.replace_one(
            {"timestamp": doc["timestamp"], "metadata.device": "esp32-wokwi"},
            doc,
            upsert=True
        )

print(f"Đã xử lý {len(sampled)} cửa sổ 10 giây; ghi/upsert vào {DATABASE}.{PROCESSED_COLLECTION}.")
print("Các bước: xử lý thiếu dữ liệu, IQR outlier, nội suy theo thời gian, resampling, rolling mean, delta, Min-Max.")
mongo.close()
