from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import pandas as pd
import joblib
import os
import hashlib
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from multisource.api import router as multisource_router

app = FastAPI(
    title="Student Academic Performance & Dropout Prediction API",
    description="Hệ thống API phục vụ tích hợp dữ liệu và dự đoán kết quả học tập",
    version="1.0.0"
)
app.include_router(multisource_router)


@app.exception_handler(RequestValidationError)
async def invalid_request(request, error):
    # Invalid NaN/Infinity inputs must return 422, without serializing those numbers.
    details = [{key: item[key] for key in ("loc", "msg", "type")} for item in error.errors()]
    return JSONResponse(status_code=422, content={"detail": details})

# Phục vụ thư mục static và route dashboard
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/dashboard")
def serve_dashboard():
    # A new script URL prevents cached frontend code from calling a newer API.
    version = hashlib.sha256(Path("static/multisource.jsx").read_bytes()).hexdigest()[:12]
    html = Path("static/index.html").read_text(encoding="utf-8")
    html = html.replace('src="/static/multisource.jsx"', f'src="/static/multisource.jsx?v={version}"')
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@app.middleware("http")
async def refresh_dashboard_assets(request, call_next):
    response = await call_next(request)
    if request.url.path in ("/dashboard", "/static/index.html", "/static/multisource.jsx"):
        response.headers["Cache-Control"] = "no-store"
    return response

# Cấu hình CORS để Frontend (React) có thể gọi API mà không bị chặn
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Đọc dữ liệu dự đoán và nạp mô hình AI đã lưu
DATA_FILE = "student_predictions.csv"
MODEL_FILE = "best_student_model.pkl"
ENCODER_FILE = "label_encoder.pkl"

if os.path.exists(DATA_FILE):
    df_students = pd.read_csv(DATA_FILE)
else:
    df_students = pd.DataFrame()

model = joblib.load(MODEL_FILE) if os.path.exists(MODEL_FILE) else None
label_encoder = joblib.load(ENCODER_FILE) if os.path.exists(ENCODER_FILE) else None


# 2. Định nghĩa schema dữ liệu đầu vào cho tính năng dự đoán trực tiếp
class StudentInput(BaseModel):
    Marital_status: int = 1
    Nationality: int = 1
    Gender: int = Field(default=1, strict=True, ge=0, le=1)
    Age_at_enrollment: int = Field(default=20, strict=True, ge=17, le=70,
        description="Tuổi nhập học nguyên, 17–70: phạm vi quan sát trong dữ liệu dùng cho model hiện tại.")
    Debtor: int = Field(default=0, strict=True, ge=0, le=1,
        description="Cờ công nợ trong nguồn: 0 = không, 1 = có; không phải nợ môn, không suy ra từ cờ học phí.")
    Tuition_fees_up_to_date: int = Field(default=1, strict=True, ge=0, le=1,
        description="Cờ học phí đã cập nhật trong nguồn: 0 = chưa, 1 = đã; độc lập với cờ công nợ.")
    Scholarship_holder: int = Field(default=0, strict=True, ge=0, le=1)
    Curricular_units_1st_sem_grade: float = Field(default=12.5, strict=True, ge=0, le=20, allow_inf_nan=False)
    Curricular_units_2nd_sem_grade: float = Field(default=13.0, strict=True, ge=0, le=20, allow_inf_nan=False)


# --- CÁC ENDPOINT API ---

@app.get("/")
def root():
    return {"message": "Student Big Data Analytics API is running successfully!"}


@app.get("/api/stats")
def get_dashboard_stats():
    """Trả về các số liệu thống kê tổng quan cho Dashboard"""
    if df_students.empty:
        return {"error": "Chưa có dữ liệu sinh viên"}

    total_students = len(df_students)
    dropout_count = int((df_students['Predicted_Target'] == 'Dropout').sum())
    graduate_count = int((df_students['Predicted_Target'] == 'Graduate').sum())
    enrolled_count = int((df_students['Predicted_Target'] == 'Enrolled').sum())

    avg_sem1 = round(float(df_students['Curricular units 1st sem (grade)'].mean()), 2)
    avg_sem2 = round(float(df_students['Curricular units 2nd sem (grade)'].mean()), 2)
    risk_rate = round((dropout_count / total_students) * 100, 2)

    return {
        "total_students": total_students,
        "dropout_predicted": dropout_count,
        "graduate_predicted": graduate_count,
        "enrolled_predicted": enrolled_count,
        "risk_rate_percent": risk_rate,
        "avg_grade_sem1": avg_sem1,
        "avg_grade_sem2": avg_sem2
    }


@app.get("/api/students")
def get_students(
    risk_only: bool = Query(False, description="Chỉ lọc các sinh viên có nguy cơ thôi học"),
    search: str = Query("", description="Tìm kiếm theo StudentID"),
    limit: int = Query(50, description="Số lượng bản ghi hiển thị")
):
    """Lấy danh sách sinh viên kèm nhãn cảnh báo để hiển thị lên bảng Table"""
    if df_students.empty:
        return []

    result_df = df_students.copy()

    if risk_only:
        result_df = result_df[result_df['Predicted_Target'] == 'Dropout']

    if search:
        result_df = result_df[result_df['StudentID'].astype(str).str.contains(search)]

    # Giới hạn số lượng bản ghi trả về để tối ưu tốc độ mạng
    result_df = result_df.head(limit)
    return result_df.to_dict(orient="records")


@app.post("/api/predict")
def predict_single_student(data: StudentInput):
    """Nhận thông tin 1 sinh viên và dự đoán nguy cơ tức thì bằng mô hình AI"""
    if model is None or label_encoder is None:
        return {"error": "Mô hình AI chưa được nạp"}

    # Tạo DataFrame đúng tên các cột như lúc huấn luyện
    input_df = pd.DataFrame([{
        'Marital_status': data.Marital_status,
        'Nationality': data.Nationality,
        'Gender': data.Gender,
        'Age_at_enrollment': data.Age_at_enrollment,
        'Debtor': data.Debtor,
        'Tuition fees up to date': data.Tuition_fees_up_to_date,
        'Scholarship holder': data.Scholarship_holder,
        'Curricular units 1st sem (grade)': data.Curricular_units_1st_sem_grade,
        'Curricular units 2nd sem (grade)': data.Curricular_units_2nd_sem_grade
    }])

    # Dự đoán
    pred_idx = model.predict(input_df)[0]
    predicted_label = label_encoder.inverse_transform([pred_idx])[0]

    risk_alert = "Cảnh báo nguy cơ thôi học" if predicted_label == "Dropout" else "Bình thường"

    return {
        "prediction": predicted_label,
        "risk_warning": risk_alert,
        "is_at_risk": predicted_label == "Dropout"
    }
