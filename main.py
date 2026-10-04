from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import joblib
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(
    title="Student Academic Performance & Dropout Prediction API",
    description="Hệ thống API phục vụ tích hợp dữ liệu và dự đoán kết quả học tập",
    version="1.0.0"
)
# Phục vụ thư mục static và route dashboard
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/dashboard")
def serve_dashboard():
    return FileResponse("static/index.html")

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
    Gender: int = 1
    Age_at_enrollment: int = 20
    Debtor: int = 0
    Tuition_fees_up_to_date: int = 1
    Scholarship_holder: int = 0
    Curricular_units_1st_sem_grade: float = 12.5
    Curricular_units_2nd_sem_grade: float = 13.0


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