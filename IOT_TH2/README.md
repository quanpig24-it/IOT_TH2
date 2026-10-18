# IoT Lab 2 — Thu thập, lưu trữ và tiền xử lý dữ liệu IoT (MongoDB Atlas)

> README được cập nhật theo **hệ thống đã triển khai thực tế**. Dự án ban đầu có Docker và MongoDB Time Series, nhưng lần thực hành này sử dụng **MongoDB Atlas** và hai **collection thông thường**. Không nên ghi rằng đã dùng Time Series collection hoặc Docker nếu chưa triển khai.

## 1. Tổng quan

Dự án mở rộng từ Bài thực hành số 1 với ESP32 mô phỏng trên Wokwi, cảm biến DHT22 (GPIO 15), HC-SR04 (TRIG GPIO 5, ECHO GPIO 18) và LED (GPIO 2). ESP32 gửi dữ liệu cảm biến định dạng JSON qua MQTT. Chương trình Python subscribe, kiểm tra dữ liệu và lưu vào MongoDB Atlas. Một script khác tiền xử lý dữ liệu và ghi kết quả sang collection riêng. Streamlit dùng để quan sát dữ liệu.

### Kiến trúc đang chạy

```text
DHT22 + HC-SR04 + ESP32 (Wokwi)
              |
              | JSON / MQTT (khoảng 5 giây/lần)
              v
      test.mosquitto.org:1883
              |
              v
 Python collector (Paho MQTT, validate)
              |
              v
 MongoDB Atlas / iot_lab2 / sensor_raw
              |
              v
 Python preprocessing (Pandas)
              |
              v
 MongoDB Atlas / iot_lab2 / sensor_processed
              |
              v
      Streamlit dashboard
```

Firmware có nhánh gửi ThingsBoard từ Lab 1, nhưng **chưa xác nhận publish thành công** ở cấu hình hiện tại vì access token còn là placeholder. Luồng MQTT dùng cho Lab 2 đã publish thành công và collector đã lưu được dữ liệu.

## 2. Công nghệ và cấu hình thực tế

| Thành phần | Cấu hình |
|---|---|
| Thiết bị | ESP32 mô phỏng Wokwi, DHT22, HC-SR04, LED |
| MQTT broker | `test.mosquitto.org` |
| MQTT port | `1883` |
| MQTT topic | `iot-lab2/phn2026/telemetry` |
| Ngôn ngữ | Python 3.11, môi trường `.venv` |
| Cơ sở dữ liệu | MongoDB Atlas, database `iot_lab2` |
| Dữ liệu thô | `sensor_raw` — collection thông thường |
| Dữ liệu đã xử lý | `sensor_processed` — collection thông thường |
| Dashboard | Streamlit, `http://localhost:8501` |

**Bảo mật:** Broker công khai trên port 1883 không mã hóa/không xác thực trong cấu hình mẫu; chỉ gửi dữ liệu mô phỏng. Không đăng tải file `.env`, MongoDB URI, mật khẩu hay ThingsBoard token. Nên đổi mật khẩu Atlas nếu URI chứa mật khẩu đã từng xuất hiện trong log hoặc được chia sẻ. Trong collector, không in nguyên URI kết nối ra terminal.

## 3. Chuẩn bị môi trường trên Windows

Mở PowerShell trong thư mục dự án:

```powershell
cd C:\Users\Admin\Downloads\iot_lab2_mongodb
```

Nếu đã có `.venv` và đã cài thư viện thì không cần cài lại. Nếu cài từ đầu:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Tạo `.env` từ `.env.example` nếu chưa có:

```powershell
Copy-Item .env.example .env
```

Sửa `.env` theo mẫu dưới đây, thay **URI bằng chuỗi kết nối Atlas của riêng bạn**:

```dotenv
MONGODB_URI=mongodb+srv://<USERNAME>:<PASSWORD>@<ATLAS_HOST>/?retryWrites=true&w=majority
MONGODB_DATABASE=iot_lab2
MONGODB_RAW_COLLECTION=sensor_raw
MONGODB_PROCESSED_COLLECTION=sensor_processed
MQTT_HOST=test.mosquitto.org
MQTT_PORT=1883
MQTT_TOPIC=iot-lab2/phn2026/telemetry
MQTT_CLIENT_ID=iotlab2-python-collector
```

> Không sao chép giá trị `<USERNAME>`, `<PASSWORD>`, `<ATLAS_HOST>` theo nghĩa đen. Không đưa `.env` lên GitHub. Atlas cần cho phép địa chỉ IP máy đang dùng trong Network Access và tài khoản database có quyền đọc/ghi.

### Kiểm tra kết nối Atlas

```powershell
@'
from dotenv import load_dotenv
from pymongo import MongoClient
import os
load_dotenv('.env')
client = MongoClient(os.environ['MONGODB_URI'], serverSelectionTimeoutMS=10000)
print('MongoDB ping:', client.admin.command('ping'))
print('Database:', os.getenv('MONGODB_DATABASE', 'iot_lab2'))
client.close()
'@ | .\.venv\Scripts\python.exe -
```

Dự án **không cần chạy `docker compose up -d`** trong cấu hình Atlas này. Các file `docker-compose.yml` và `mongo-init/` (nếu vẫn còn) thuộc phương án MongoDB local ban đầu, không phải bước bắt buộc của quy trình hiện tại.

## 4. Chạy Wokwi và MQTT

1. Mở dự án Wokwi Lab 1: https://wokwi.com/projects/475646519126421505
2. Sử dụng firmware Lab 2 trong `firmware/sketch.ino` cùng sơ đồ mạch tương ứng.
3. Kiểm tra firmware publish đến `test.mosquitto.org:1883`, topic `iot-lab2/phn2026/telemetry` (phải trùng `.env`).
4. Bắt đầu mô phỏng; xem Serial Monitor. Dòng `Lab 2 MQTT publish: OK` cho biết firmware đã publish thành công đến broker dùng cho Lab 2.
5. Thay đổi giá trị DHT22/HC-SR04 trên Wokwi để tạo dữ liệu thử nghiệm.

Payload JSON đã dùng gồm các trường số:

```json
{
  "temperature": 28.5,
  "humidity": 65.0,
  "distance_cm": 42.3,
  "rssi": -55,
  "sequence": 1,
  "uptime_s": 12
}
```

Giá trị trên chỉ là **ví dụ cấu trúc**, không phải một bản ghi đã đo. Firmware hiện tại có thể **chưa gửi `timestamp_ms`**; khi đó collector thông báo `chưa có timestamp NTP` và không thể tính độ trễ đầu-cuối đáng tin cậy.

## 5. Chạy pipeline

Mỗi chương trình có thể chạy ở một cửa sổ PowerShell riêng, cùng thư mục dự án.

### Bước 1 — Collector MQTT → MongoDB Atlas

```powershell
.\.venv\Scripts\python.exe collector/mqtt_to_mongodb.py
```

Giữ collector đang chạy, đồng thời bật Wokwi. Terminal sẽ xuất hiện các dòng `[SAVED] seq=...` khi nhận và lưu thành công. Collection `iot_lab2.sensor_raw` chứa dữ liệu cảm biến gốc, timestamp nhận và metadata của thiết bị/topic.

**Lưu ý:** Nếu terminal in nguyên MongoDB URI, sửa dòng log trong `collector/mqtt_to_mongodb.py` để chỉ in tên database/collection, tránh lộ mật khẩu.

### Bước 2 — Tiền xử lý

```powershell
.\.venv\Scripts\python.exe preprocessing/preprocess.py
```

Script đọc dữ liệu trong khoảng 24 giờ gần nhất và thực hiện các bước theo code dự án: xử lý dữ liệu thiếu, phát hiện ngoại lệ bằng IQR, nội suy, resampling cửa sổ 10 giây, rolling mean, delta và chuẩn hóa Min-Max. Kết quả được upsert vào `iot_lab2.sensor_processed`.

Một lần chạy đã ghi nhận thông báo: **`Đã xử lý 3 cửa sổ 10 giây; ghi/upsert vào iot_lab2.sensor_processed.`** Chạy lại sau khi thu thập thêm dữ liệu sẽ cho kết quả khác.

### Bước 3 — Dashboard

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard/app.py
```

Mở `http://localhost:8501`. Quan sát chỉ số, biểu đồ và dữ liệu thô/đã xử lý. Nếu giao diện có nút **Làm mới dữ liệu**, bấm để truy vấn lại dữ liệu mới.

## 6. Thiết kế dữ liệu MongoDB

### `sensor_raw`

Các trường được collector lưu gồm:

- `timestamp`: thời gian nhận phía collector (UTC).
- `received_at`: thời gian nhận (UTC).
- `metadata.device`: định danh thiết bị, ví dụ `esp32-wokwi`.
- `metadata.topic`: MQTT topic.
- `payload_valid`: cờ kiểm tra payload.
- `payload_size_bytes`: kích thước MQTT payload.
- Các trường số từ telemetry như `temperature`, `humidity`, `distance_cm`, `rssi`, `sequence`, `uptime_s` nếu có trong payload.

### `sensor_processed`

Collection lưu kết quả tổng hợp theo cửa sổ 10 giây và các đặc trưng do script preprocessing tính toán. Xem trực tiếp document trong Atlas để xác nhận **tên trường đầu ra cụ thể** theo phiên bản script đang chạy.

### Time Series và retention

**Trạng thái thực tế:** Hai collection hiện được tạo là **collection thông thường**, chưa phải MongoDB Time Series collection. Chưa xác nhận đã cấu hình retention/TTL. Nếu cần đáp ứng đầy đủ yêu cầu đề bài, có thể chuyển sang Time Series collection và thiết lập chính sách lưu giữ dữ liệu phù hợp; việc này là **đề xuất cải tiến**, không phải kết quả đã hoàn thành.

Đối với mất/trùng bản tin: cần đánh giá chuỗi `sequence` và bổ sung cơ chế chống trùng (ví dụ unique key theo device + sequence hoặc cơ chế upsert phù hợp). Chưa có số đo tỷ lệ mất bản tin đáng tin cậy.

## 7. Kiểm tra dung lượng bằng `collStats`

Chạy lệnh sau tại thư mục dự án:

```powershell
@'
from dotenv import load_dotenv
from pymongo import MongoClient
import os

load_dotenv('.env')
client = MongoClient(os.environ['MONGODB_URI'])
db = client[os.getenv('MONGODB_DATABASE', 'iot_lab2')]

for name in ['sensor_raw', 'sensor_processed']:
    stats = db.command('collStats', name, scale=1)
    data = stats.get('size', 0)
    index = stats.get('totalIndexSize', 0)
    print(f'\nCollection: {name}')
    print(f"So document: {stats.get('count', 0)}")
    print(f'Dung luong du lieu: {data:,} bytes ({data / 1024:.2f} KB)')
    print(f'Dung luong index: {index:,} bytes ({index / 1024:.2f} KB)')
    print(f'Tong data + index: {data + index:,} bytes ({(data + index) / 1024:.2f} KB)')

client.close()
'@ | .\.venv\Scripts\python.exe -
```

**Kết quả đã đo tại một thời điểm:**

| Chỉ số | `sensor_raw` | `sensor_processed` |
|---|---:|---:|
| Số document | 24 | 3 |
| Dung lượng dữ liệu | 6,936 bytes (6.77 KB) | 1,557 bytes (1.52 KB) |
| Dung lượng index | 36,864 bytes (36.00 KB) | 36,864 bytes (36.00 KB) |
| Tổng data + index | 43,800 bytes (42.77 KB) | 38,421 bytes (37.52 KB) |

Đây là **ảnh chụp trạng thái tại thời điểm đo**, không phải số liệu cố định; số lượng document và dung lượng sẽ thay đổi. `size + totalIndexSize` là tổng kích thước logic dữ liệu và chỉ mục theo thống kê collection, **không đồng nghĩa dung lượng vật lý toàn cluster Atlas**.

## 8. Độ trễ, tốc độ và tính toàn vẹn

- **Chu kỳ publish cấu hình:** khoảng 5 giây/bản tin, tương đương lý thuyết khoảng 12 bản tin/phút nếu chạy liên tục và không mất gói.
- **Thông lượng thực tế:** cần đo `count_documents` ở hai thời điểm cách nhau một khoảng xác định, sau đó tính `(count_sau - count_truoc) / thời_gian`.
- **Độ trễ end-to-end:** hiện **chưa đo được chính xác** vì payload thiếu timestamp phát từ ESP32 được đồng bộ NTP. Không lấy thời gian giữa hai bản tin làm độ trễ.
- **Độ trễ ghi database:** có thể đo riêng bằng `time.perf_counter()` trước/sau `insert_one()`; đây là thời gian ghi DB, **không phải** độ trễ end-to-end.
- **Tính toàn vẹn:** dùng trường `sequence` để kiểm tra các số bị thiếu hoặc lặp trong cùng một phiên; cần phân biệt thiết bị reset sequence khi khởi động lại.

## 9. Minh chứng cần chụp cho báo cáo

1. **Wokwi:** sơ đồ nối ESP32/DHT22/HC-SR04/LED.
2. **Serial Monitor:** JSON telemetry và `Lab 2 MQTT publish: OK`.
3. **Collector:** terminal có MQTT subscribe và nhiều dòng `[SAVED]` (che URI/mật khẩu nếu log có in).
4. **Atlas `sensor_raw`:** document chứa dữ liệu cảm biến và metadata.
5. **Preprocessing:** terminal chạy script thành công.
6. **Atlas `sensor_processed`:** document sau xử lý, các đặc trưng đã tạo.
7. **Streamlit:** giao diện dashboard có chỉ số và biểu đồ.
8. **`collStats`:** kết quả hai collection cùng số document, data size và index size.
9. **Đánh giá hiệu năng:** ảnh log collector hoặc phép đo số document theo khoảng thời gian; **không ghi là ảnh độ trễ end-to-end nếu chưa đo được**.

## 10. Cấu trúc dự án

```text
iot_lab2_mongodb/
├── firmware/                 # Firmware ESP32/Wokwi
├── collector/
│   └── mqtt_to_mongodb.py    # Subscribe MQTT, validate và lưu raw
├── preprocessing/
│   └── preprocess.py         # Làm sạch, resample và ghi processed
├── dashboard/
│   └── app.py                # Dashboard Streamlit
├── requirements.txt
├── .env.example              # Cấu hình mẫu
├── .env                      # Cấu hình thật, KHÔNG commit
├── .venv/                    # Python virtual environment
├── docker-compose.yml        # Phương án Docker cũ, không dùng khi chạy Atlas
└── mongo-init/               # Script khởi tạo MongoDB local cũ (nếu còn)
```

## 11. Trạng thái hoàn thành và hướng cải tiến

**Đã xác nhận:** MQTT publish từ Wokwi đến broker Lab 2, collector lưu raw lên Atlas, preprocessing ghi processed, dashboard chạy, đo dung lượng bằng `collStats`.

**Chưa xác nhận/hoàn thiện:** ThingsBoard publish, MongoDB Time Series collection, retention policy, chống trùng/mất bản tin có kiểm thử, độ trễ end-to-end và thông lượng dài hạn.

**Hướng cải tiến:** đồng bộ NTP và gửi `timestamp_ms` từ ESP32; tạo collection Time Series và retention/TTL; bổ sung kiểm thử sequence, retry và chống trùng; dùng MQTT có TLS/xác thực trong môi trường thực; bổ sung phép đo hiệu năng theo thời gian và bảo vệ thông tin đăng nhập Atlas.

## 12. Yêu cầu nộp bài

Theo đề Bài thực hành số 2: mã nguồn firmware, collector, preprocessing, file cấu hình mẫu và README; báo cáo Word 4–6 trang gồm sơ đồ kiến trúc, schema, kết quả thực nghiệm, phân tích độ trễ/lưu trữ, khó khăn và cải tiến; cùng ứng dụng dashboard để demo. Không commit `.env`, mật khẩu Atlas hoặc ThingsBoard token lên GitHub.
