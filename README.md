# Face Attendance System

**Duo AI – AntelopeV2**

Hệ thống điểm danh và nhận diện khuôn mặt thời gian thực, được tối ưu GPU với kiến trúc **Duo AI**:

* **Face Detection:** SCRFD
* **Face Recognition:** Glint360k ResNet-100
* **Database:** MySQL
* **Backend:** Python FastAPI

---

## 1. Yêu cầu hệ thống

| Thành phần    | Yêu cầu                               |
| ------------- | --------------------------------------|
| Hệ điều hành  | Windows 10/11 hoặc Linux              |
| Python        | Bất kỳ, miễn chạy được setup_venv.py  |
| GPU           | Khuyến nghị GPU NVIDIA hỗ trợ CUDA    |
| Cơ sở dữ liệu | MySQL                                 |

> **Lưu ý:** GPU NVIDIA được khuyến nghị để đạt hiệu năng nhận diện khuôn mặt theo thời gian thực.

---

## 2. Cài đặt môi trường

Mở Terminal tại **thư mục gốc của dự án**, sau đó thực hiện các bước sau.

### Bước 1: Tạo môi trường Python

**Windows / Linux:**

```bash
python firstRun/setup_venv.py
```

### Bước 2: Kích hoạt môi trường ảo

**Windows:**

```powershell
.venv\Scripts\activate
```

**Linux:**

```bash
source .venv/bin/activate
```

### Bước 3: Cài đặt thư viện và tải model

Chạy script tự động để cài đặt các thư viện cần thiết và tải model AntelopeV2:

```bash
python firstRun/setup_package.py
```

---

## 3. Kiểm tra hệ thống

Thực hiện lần lượt các lệnh sau để kiểm tra kết nối cơ sở dữ liệu, GPU và môi trường hoạt động.

### 3.1. Kiểm tra kết nối MySQL

```bash
python -m firstRun.test_db
```

### 3.2. Kiểm tra khả năng sử dụng GPU

```bash
python -m firstRun.testGPU
```

### 3.3. Kiểm tra tổng thể môi trường

```bash
python -m firstRun.checkEnv
```

---

## 4. Vận hành hệ thống

Tại thư mục gốc của dự án, chạy lệnh:

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Sau khi máy chủ khởi động thành công, truy cập hệ thống bằng trình duyệt:

```text
http://localhost:8000
```

### Nhận diện tầm xa qua IP Webcam

Trình duyệt hiển thị luồng `/video` của IP Webcam và gửi frame qua WebSocket `/ws/recognize`. Frame dùng để phát hiện được thu nhỏ cạnh dài tối đa còn 960 pixel, mã hóa JPEG ở chất lượng 0,7. Khi cần xác minh khuôn mặt, backend yêu cầu trình duyệt gửi thêm một frame độ phân giải gốc lấy từ hình đang hiển thị. Hệ thống không gọi `/photoaf.jpg`, tránh yêu cầu điện thoại chụp ảnh riêng làm gián đoạn video.

#### Luồng phát hiện và theo dõi

1. Trình duyệt chỉ gửi frame tiếp theo sau khi nhận được phản hồi cho frame trước. Cách này giữ tối đa một frame đang được backend xử lý, tránh tích tụ frame cũ khi nhận diện chậm.
2. Backend giải mã JPEG và chuyển frame cho pipeline. Pipeline chỉ chạy phát hiện trên **mỗi frame thứ hai nhận được**; frame xen kẽ được bỏ qua cho bước phát hiện và trả lại kết quả theo dõi hiện có.
3. InsightFace với model AntelopeV2 tìm khuôn mặt trong frame đã cân chỉnh sáng/tương phản. Pipeline bỏ detection có điểm tin cậy dưới 0,35 hoặc cạnh ngắn dưới 8 pixel.
4. Detection giữa các lần phân tích được ghép thành track dựa trên độ chồng lấp, khoảng cách tâm và thay đổi kích thước khuôn mặt. Track cần xuất hiện trong ít nhất **hai lần phát hiện** trước khi đủ điều kiện xác minh bằng frame độ phân giải gốc. Đây là hai frame được phân tích, không nhất thiết là hai frame gửi liên tiếp.

#### Khi nào gửi frame độ phân giải gốc và cách xác minh

- Track chưa được xác nhận danh tính có thể yêu cầu frame độ phân giải gốc khi đã được phát hiện ít nhất hai lần, còn lượt thử và chưa đến trạng thái kết thúc. Một track được thử lại sau tối thiểu 2 giây. Track ngừng được gửi xác minh sau tối đa 6 lượt xử lý hoặc 10 frame bị từ chối. Worker chỉ xử lý một job tại một thời điểm và có giới hạn tối thiểu 1 giây giữa các lần nhận job trên toàn pipeline.
- Mỗi frame độ phân giải gốc có thể phục vụ tối đa **hai track**. Tọa độ track từ frame video được quy đổi theo kích thước frame này, sau đó backend cắt vùng quanh từng khuôn mặt. Backend chỉ tăng cường sáng/tương phản trên vùng đã cắt, không xử lý toàn bộ ảnh độ phân giải cao.
- InsightFace tìm lại khuôn mặt trong vùng cắt và chọn khuôn mặt gần tâm vùng nhất. Ảnh bị loại nếu không tìm thấy mặt hoặc độ sắc nét dưới ngưỡng 30. Embedding từ ảnh đạt yêu cầu được cộng dồn theo trọng số dựa trên điểm phát hiện, kích thước và độ sắc nét.
- Embedding tổng hợp được so với các embedding đã lưu. Độ tương đồng từ 0,50 trở lên và khuôn mặt ít nhất 40 pixel được xác nhận. Nếu chưa đủ điều kiện xác nhận nhưng độ tương đồng từ 0,42 trở lên, track được giữ ở trạng thái ứng viên. Ảnh có độ tương đồng thấp hơn tiếp tục ở trạng thái chờ cho tới giới hạn thử.
- Sau khi xác nhận, hệ thống ghi điểm danh tối đa một lần mỗi người trong 60 giây. Giao diện hiện hộp và tên cho khuôn mặt đã xác nhận; tọa độ hộp được đổi về kích thước video gốc để overlay khớp với hình hiển thị.

Điện thoại và máy chạy backend cần truy cập được với nhau qua mạng. Frame độ phân giải gốc và frame video nên có cùng tỷ lệ khung hình để tọa độ cắt vùng mặt chính xác. Độ phân giải gốc giúp có thêm chi tiết khi khuôn mặt ở xa; chỉ frame cần xác minh mới được gửi ở độ phân giải này.

### Truy cập từ thiết bị khác trong cùng mạng

Sử dụng địa chỉ IP của máy tính chạy hệ thống:

```text
http://<IP-MAY-TINH>:8000
```

Ví dụ:

```text
http://192.168.1.100:8000
```

---

## 5. Cấu trúc thư mục dự án

```text
HTTM2/
├── backend/
├── frontend/
├── models/
├── runtime/
├── .venv/
└── firstRun/
    ├── setup_venv.py
    ├── setup_package.py
    ├── test_db.py
    ├── testGPU.py
    └── checkEnv.py
```

---

## 6. Công nghệ sử dụng

* **Ngôn ngữ:** Python
* **Framework:** FastAPI
* **Face Detection:** SCRFD
* **Face Recognition:** Glint360k ResNet-100
* **Model:** AntelopeV2
* **Database:** MySQL
* **GPU Acceleration:** NVIDIA CUDA
* **Server:** Uvicorn
