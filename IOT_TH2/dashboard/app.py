import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
st.set_page_config(page_title="IoT Lab 2 Monitor", layout="wide")
st.title("IoT Lab 2 — Giám sát dữ liệu cảm biến")
st.caption("ESP32/Wokwi · MQTT · MongoDB Time Series · dữ liệu thô và dữ liệu đã tiền xử lý")

URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE = os.getenv("MONGODB_DATABASE", "iot_lab2")
RAW_COLLECTION = os.getenv("MONGODB_RAW_COLLECTION", "sensor_raw")
PROCESSED_COLLECTION = os.getenv("MONGODB_PROCESSED_COLLECTION", "sensor_processed")

try:
    mongo = MongoClient(URI, serverSelectionTimeoutMS=3000)
    mongo.admin.command("ping")
    db = mongo[DATABASE]
except Exception as exc:
    st.error(f"Không kết nối được MongoDB: {exc}")
    st.stop()

window_label = st.selectbox("Khoảng thời gian", ["1 giờ", "6 giờ", "24 giờ"], index=0)
hours = {"1 giờ": 1, "6 giờ": 6, "24 giờ": 24}[window_label]
cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

if st.button("Làm mới dữ liệu"):
    st.rerun()

raw_docs = list(db[RAW_COLLECTION].find(
    {"timestamp": {"$gte": cutoff}},
    {"_id": 0}
).sort("timestamp", 1))
processed_docs = list(db[PROCESSED_COLLECTION].find(
    {"timestamp": {"$gte": cutoff}},
    {"_id": 0}
).sort("timestamp", 1))
raw = pd.DataFrame(raw_docs)
processed = pd.DataFrame(processed_docs)

if raw.empty:
    st.warning("Chưa có dữ liệu thô. Hãy chạy firmware Wokwi và collector.")
else:
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True)
    latest = raw.sort_values("timestamp").iloc[-1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nhiệt độ", f"{float(latest.get('temperature', float('nan'))):.2f} °C")
    c2.metric("Độ ẩm", f"{float(latest.get('humidity', float('nan'))):.2f} %RH")
    c3.metric("Khoảng cách", f"{float(latest.get('distance_cm', float('nan'))):.2f} cm")
    c4.metric("Số bản ghi", str(len(raw)))

    st.subheader("Dữ liệu thô theo thời gian")
    long = raw.melt(
        id_vars=["timestamp"],
        value_vars=[c for c in ["temperature", "humidity", "distance_cm"] if c in raw.columns],
        var_name="Đại lượng",
        value_name="Giá trị"
    )
    if not long.empty:
        st.plotly_chart(px.line(long, x="timestamp", y="Giá trị", color="Đại lượng",
                                title="Telemetry thô"), use_container_width=True)

    if "timestamp_ms" in raw.columns:
        valid = raw[raw["timestamp_ms"].fillna(0) > 0].copy()
        if not valid.empty:
            valid["Độ trễ ước lượng (ms)"] = (
                valid["timestamp"].astype("int64") / 1e6 - valid["timestamp_ms"]
            )
            latency = valid["Độ trễ ước lượng (ms)"]
            st.subheader("Độ trễ đầu-cuối ước lượng")
            st.write(f"Trung bình: **{latency.mean():.1f} ms** · Trung vị: **{latency.median():.1f} ms** · Mẫu: **{len(latency)}**")
            st.caption("Kết quả phụ thuộc độ chính xác đồng bộ NTP giữa ESP32 và máy chạy collector.")

st.divider()
st.subheader("Dữ liệu đã tiền xử lý")
if processed.empty:
    st.info("Chưa có dữ liệu xử lý. Chạy: python preprocessing/preprocess.py")
else:
    processed["timestamp"] = pd.to_datetime(processed["timestamp"], utc=True)
    columns = [c for c in ["temperature", "humidity", "distance_cm"] if c in processed.columns]
    if columns:
        long2 = processed.melt(id_vars=["timestamp"], value_vars=columns,
                                var_name="Đại lượng", value_name="Giá trị")
        st.plotly_chart(px.line(long2, x="timestamp", y="Giá trị", color="Đại lượng",
                                title="Dữ liệu sau resampling 10 giây"), use_container_width=True)
    st.dataframe(processed.tail(20), use_container_width=True)

with st.expander("Bảng dữ liệu thô gần nhất"):
    if not raw.empty:
        st.dataframe(raw.sort_values("timestamp", ascending=False).head(30), use_container_width=True)

mongo.close()
