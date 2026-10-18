# Student Big Data Analytics

## Clone và chạy trên máy mới

Cần Git, Python **3.11** và kết nối mạng để cài thư viện/tải các thư viện giao
diện từ CDN. Repository đã kèm model, encoder, CSV dự đoán và các bảng tổng
hợp Spark/metadata để mở đủ 5 mục. **Không cần Docker, MySQL, MongoDB, chạy
ETL, Spark hoặc huấn luyện lại model để xem dashboard.**

Windows PowerShell:

```powershell
git clone https://github.com/caohienITT05/student-bigdata-analytics.git
cd student-bigdata-analytics
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

macOS/Linux (đã có Python 3.11):

```bash
git clone https://github.com/caohienITT05/student-bigdata-analytics.git
cd student-bigdata-analytics
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Mở **http://127.0.0.1:8000/dashboard** trên máy vừa chạy server. Địa chỉ
127.0.0.1 luôn trỏ đến chính máy đang sử dụng, không phải một website đã host.
Nếu cổng 8000 bận có thể đổi `--port 8001`; frontend dùng API cùng địa chỉ
với trang đang mở. Lần sau không cần cài lại, chỉ chạy lệnh uvicorn. Dừng bằng
Ctrl+C. Nếu Windows không có lệnh `py`, dùng `python` sau khi kiểm tra phiên
bản bằng `python --version`.

Các CSV Kaggle/OULAD thô và Parquet trung gian dung lượng lớn không nằm trong
Git. Dashboard đọc bản xuất `data/curated/dashboard.sqlite` cùng tám báo cáo
JSON cần thiết trong `reports/data_pipeline/`. Các con số là kết quả batch
đã lưu, không phải dữ liệu đang thu thập trực tiếp. Muốn chạy lại pipeline,
cần chuẩn bị đầy đủ các file nguồn theo bảng bên dưới và bật Docker Desktop.

## Dashboard hiện tại

Năm mục dùng thanh điều hướng sticky, mỗi lần chỉ hiện một mục. Bộ lọc và
phân trang giữ nguyên khi chuyển mục; URL hash giữ mục khi tải lại.

- **Tổng quan**: mục tiêu và quy mô riêng của dataset gốc, Kaggle, OULAD.
- **Kết quả học tập**: chỉ lọc nguồn; giữ các thẻ số liệu, bảng đối chiếu nguồn,
  phân bố Target, tuổi và điểm hai học kỳ. Không có bộ lọc nhãn/loại dữ liệu
  hoặc các bảng tỷ lệ đạt, chênh lệch điểm, học phí/học bổng.
- **Hành vi OULAD**: chỉ phân tích cả học phần; lọc học phần và đợt, thống kê
  lượt học/người học/lượt nhấp/không tương tác, kết quả và hoạt động theo tuần.
  Giữ bảng hoạt động theo nhóm; không có phạm vi sớm, quy tắc ít hoạt động,
  bảng đánh giá, điểm hoặc nộp muộn.
- **Dự đoán & tra cứu**: giữ nguyên form Random Forest, thống kê, biểu đồ,
  tìm mã, lọc nguy cơ và phân trang 20 dòng trong tối đa 100 kết quả tải về.
  Target gốc và dự đoán mô hình là hai cột riêng.
- **Chất lượng dữ liệu**: có khối **Dữ liệu sử dụng có những gì?**, chọn nguồn
  Dataset gốc/Kaggle/OULAD, chọn một trong 10 file CSV, nhóm thông tin và xem
  tên tiếng Việt, tên cột gốc, dạng dữ liệu. Bảng phân trang 8 trường;
  số dòng/cột và header lấy từ manifest nguồn, không tự sinh ID hoặc nhãn test.
  Thống kê ô thiếu, cờ lỗi, dòng/khóa trùng và khóa thiếu nằm trong phần thu gọn
  **Chất lượng theo nguồn và file**. Kiểm tra JOIN, cấu hình/thời gian Spark và
  bảng file kết quả nằm chung trong **Chi tiết kỹ thuật**, mặc định đóng.
  Không có bảng mã danh mục.

Danh mục trường là phần mô tả cấu trúc nguồn; không mở lại các bảng phân tích
điểm/nộp muộn đã bỏ. Nhãn/nhóm nằm trong `config/data_dictionary.json`; API
đối chiếu với các cột có thật trong manifest và vẫn hiện cột mới chưa chú giải.
Các mã quốc tịch, nghề nghiệp được ghi là mã, không tự diễn giải tên chưa xác minh.

Các tính toán và API riêng cho các phần đã bỏ cũng được gỡ. Dữ liệu nguồn,
model, encoder và pipeline MySQL/MongoDB cũ được giữ nguyên. Những output và
báo cáo lịch sử không còn sử dụng có thể vẫn tồn tại trên đĩa; chúng không
được dùng làm nguồn chức năng đã bỏ trên dashboard.

Form dự đoán ẩn ô công nợ và giữ `Debtor=0`. Ô điểm trung bình hai học kỳ tự
tính để hiển thị, không thay thế đặc trưng hoặc thay đổi model.

## Chạy ứng dụng (PowerShell, tại thư mục dự án)

```powershell
cd D:\BigData\student-bigdata-analytics
.\scripts\run-app.ps1
# Hoặc:
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Dashboard: http://127.0.0.1:8000/dashboard

Swagger: http://127.0.0.1:8000/docs

Ứng dụng dùng Python 3.11 và môi trường `.venv` hiện có. Khi tạo môi trường
mới cài `requirements.txt`; giữ phiên bản scikit-learn tương thích model đã
lưu. React, Babel, Tailwind và Chart.js tải từ CDN nên trình duyệt cần mạng.
Không cần npm build. Docker chỉ cần khi chạy Spark hoặc pipeline database;
việc mở dashboard sử dụng file đã xuất và model có sẵn trong Git.

## Nguồn dữ liệu

| Nguồn/file | Số dòng | Đơn vị |
|---|---:|---|
| `data/raw/original/dataset.csv` | 4.424 | Hồ sơ quan sát |
| `data/raw/kaggle_s4e6/train.csv` | 76.518 | Bản ghi sinh, có Target |
| `data/raw/kaggle_s4e6/test.csv` | 51.012 | Bản ghi sinh, không có Target |
| `data/raw/oulad/courses.csv` | 22 | Học phần × đợt |
| `data/raw/oulad/studentInfo.csv` | 32.593 | Lượt học |
| `data/raw/oulad/studentRegistration.csv` | 32.593 | Đăng ký lượt học |
| `data/raw/oulad/vle.csv` | 6.364 | Tài nguyên |
| `data/raw/oulad/studentVle.csv` | 10.655.280 | Tương tác theo người/tài nguyên/ngày |
| `data/raw/oulad/assessments.csv` | 206 | Định nghĩa bài đánh giá |
| `data/raw/oulad/studentAssessment.csv` | 173.912 | Bản ghi bài nộp |

`dataset.csv` ở root là cùng nguồn với bản trong `data/raw/original`.
`OULAD.names` giữ tài liệu nguồn (Windows-1252). Manifest trong
`reports/data_pipeline/sources_manifest.json` ghi số dòng/cột, header,
delimiter, kích thước và SHA-256. Không cộng các nguồn thành số sinh viên thật.

## Spark batch và các tầng dữ liệu

`config/data_sources.json` cấu hình đường dẫn và tài nguyên Spark.

- `data/clean/`: Parquet chuẩn hóa từng nguồn và `quarantine/`.
- `data/curated/academic_records/`: 131.954 bản ghi tích hợp theo tên cột,
  giữ mọi thuộc tính nguồn và thông tin truy vết; không JOIN danh tính giữa nguồn.
- `data/curated/oulad_enrolments/`: hồ sơ theo
  `id_student + code_module + code_presentation`, ghép hoạt động cả học phần.
- `data/curated/oulad_weekly/`: hoạt động theo tuần của cả học phần.
- `data/curated/aggregates/`: sáu bảng tổng hợp Spark SQL hiện dùng:
  `a_summary`, `a_target`, `a_histograms`, `b_population`, `b_results`, `b_weekly`.
- `data/curated/dashboard.sqlite`: bản xuất bảng tổng hợp cho API đọc nhanh.
- `reports/data_pipeline/`: báo cáo chất lượng, runtime và kiểm chứng.
- Các thư mục `smoke/` chỉ là output thử riêng, không phục vụ dashboard.

Kaggle test luôn giữ Target null; không lấy dự đoán thay nhãn. Tỷ lệ Dropout
chỉ dùng mẫu số có nhãn. Điểm 0 và dòng trùng được giữ, không tự điền trung
bình ở nhánh Spark. Mã danh mục giữ nguyên theo nguồn; chưa có ánh xạ được
xác minh giữa dataset gốc và Kaggle.

OULAD giữ lượt học không tương tác. Ngày âm là trước ngày bắt đầu; tuần bằng
floor(ngày/7). Bảng sự kiện được tổng hợp trước khi LEFT JOIN hồ sơ, tránh
nhân số dòng. Bảng đánh giá vẫn được đọc để kiểm tra chất lượng và khóa JOIN,
không tạo các chỉ số điểm/nộp muộn phục vụ phân tích. Withdrawn là rút học
phần, khác Dropout. Các so sánh hồi cứu không chứng minh quan hệ nhân quả.

Spark 4.0.1 chạy `local[2]` trong image `apache/spark:4.0.1-python3`, trên một
máy, không phải cluster nhiều máy. Nguồn/model được mount read-only; chỉ
clean/curated/reports được ghi. Không thu toàn bộ VLE về Pandas/driver.

```powershell
# Cần Docker Desktop Linux containers khi xử lý batch.
.\scripts\run-pipeline.ps1 -Stage smoke
.\scripts\run-pipeline.ps1 -Stage all
.\scripts\run-pipeline.ps1 -Stage verify
```

Các bước `prepare`, `a`, `oulad`, `sql` cũng chạy riêng được; `sql` yêu cầu hai
nhánh đầu đã cập nhật. Fingerprint giúp bỏ qua bước không đổi. Dùng `-Force`
nếu cần xử lý lại. Không cần chạy Spark để đổi bộ lọc trên dashboard.

## API

- `GET /api/multi/catalog`: mô tả trường của 10 CSV nguồn; chỉ đọc metadata,
  không quét dữ liệu lớn hoặc chạy Spark. Trả 503 nếu thiếu manifest nguồn.
- `GET /api/multi/status`: nguồn, chất lượng và thông tin kỹ thuật hiện dùng.
- `GET /api/multi/academic/summary?source=original`: chỉ lọc theo source
  (`all`, `original`, `kaggle_train`, `kaggle_test`).
- `GET /api/multi/oulad/summary?module=AAA&presentation=2013J`: cả học phần.
- `GET /api/multi/reports/{name}`: các báo cáo được cho phép.
- `GET /api/stats`, `GET /api/students`, `POST /api/predict`: chức năng model cũ.

API bảng phân tích chi tiết học tập/OULAD đã gỡ (404); `/catalog` chỉ mô tả
cấu trúc trường nguồn. Tham số nhãn, loại dữ liệu và
phạm vi thời gian không còn hỗ trợ; gửi các tham số cũ trả 422 để tránh
hiểu nhầm kết quả đã được lọc. API đọc SQLite read-only, không import Spark.
Khi thiếu output đầy đủ, API phân tích trả 503 rõ ràng.

## Pipeline dự đoán ban đầu (giữ nguyên)

`split_data.py` tạo StudentID giả lập và tách dataset gốc thành
`mysql_demographics.csv`, `mongodb_behaviors.json`, `flat_grades.csv`.
`import_data.py` nhập vào MySQL/MongoDB; `etl_pipeline.py` ghép ba nguồn theo
StudentID, xử lý giá trị thiếu và xuất `final_dataset.csv` với chín đầu vào.

`train_models.py` chia phân tầng 80/20, so sánh Decision Tree, Random Forest,
XGBoost và lưu model tốt nhất. Model hiện có là Random Forest (100 cây,
max_depth=8); `label_encoder.pkl` giải mã nhãn. `student_predictions.csv`
chứa Target gốc, Predicted_Target và Risk_Warning cho 4.424 hồ sơ.
Model không sử dụng Kaggle/OULAD; điểm hai học kỳ là đầu vào nên không gọi
đây là dự đoán ngay tại thời điểm nhập học. Dự đoán toàn bộ file không phải
đánh giá trên tập kiểm thử độc lập.

Form và API dự đoán chỉ chấp nhận tuổi nhập học nguyên 17–70 (phạm vi tuổi
trong dữ liệu của model), điểm hữu hạn 0–20, và các cờ công nợ/học phí/học
bổng/giới tính là 0 hoặc 1. Tuổi/điểm trống trong form không tự chuyển thành 0;
giá trị không hợp lệ bị chặn trước khi dự đoán, API trả 422. Công nợ (Debtor)
không phải nợ môn; cờ công nợ và học phí được giữ độc lập theo nguồn, không
tự ép thành hai giá trị đối nghịch. Thay đổi đầu vào xóa kết quả dự đoán cũ.

Không cần chạy lại import/ETL/training để phục vụ dashboard. Đặc biệt
`import_data.py` xóa bảng/collection trước khi nhập; chỉ chạy khi chủ động
xây dựng lại database đúng mục đích. Không xóa volume hoặc dừng container dự
án khác. Docker Compose cũ dùng MySQL cổng 3307 và MongoDB cổng 27017.

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe tests\test_multisource.py
node tests\browser.cjs
```

Browser test cần Playwright trên NODE_PATH (có thể dùng runtime bundled),
Edge hiện có. Kiểm tra API đối chiếu SQL, nhãn test, API đã gỡ, checksum nguồn,
model cũ, dự đoán/tìm kiếm/lọc. Browser kiểm tra năm mục, bộ lọc còn lại,
biểu đồ, chi tiết kỹ thuật thu gọn, phân trang, hash/reload/back-forward,
màn hình 390px và lỗi console. Biên bản lần tinh gọn có tiền tố `trim-`.

`tests/test_multisource.py` là kiểm tra đầy đủ cả nguồn thô và batch nên cần
các file Kaggle/OULAD đã tải. Các file thô không bắt buộc để chạy ứng dụng.
