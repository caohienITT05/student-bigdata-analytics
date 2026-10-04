import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, classification_report

print("=== BẮT ĐẦU HUẤN LUYỆN VÀ ĐÁNH GIÁ MÔ HÌNH HỌC MÁY ===")

# 1. Đọc dữ liệu đã tích hợp
df = pd.read_csv("final_dataset.csv")

# 2. Tiền xử lý dữ liệu
# Tách các đặc trưng (X) và nhãn dự đoán (y)
X = df.drop(columns=['StudentID', 'Target'])
y_raw = df['Target']

# Mã hóa nhãn Target (Dropout, Enrolled, Graduate) thành số nguyên 0, 1, 2
le = LabelEncoder()
y = le.fit_transform(y_raw)
class_names = le.classes_
print(f"Các lớp nhãn phân loại: {list(enumerate(class_names))}")

# 3. Phân chia tập dữ liệu: 80% Train, 20% Test
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"Số lượng mẫu huấn luyện (Train): {X_train.shape[0]}")
print(f"Số lượng mẫu kiểm thử (Test): {X_test.shape[0]}")

# 4. Khởi tạo 3 mô hình học máy
models = {
    "Decision Tree": DecisionTreeClassifier(max_depth=5, random_state=42),
    "Random Forest": RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42),
    "XGBoost": XGBClassifier(n_estimators=100, learning_rate=0.1, max_depth=4, random_state=42, eval_metric='mlogloss')
}

accuracies = {}
trained_models = {}

# 5. Huấn luyện và đánh giá từng mô hình
print("\n--- KẾT QUẢ ĐÁNH GIÁ TRÊN TẬP TEST ---")
for name, model in models.items():
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    accuracies[name] = acc
    trained_models[name] = model
    print(f"\n[{name}] Accuracy: {acc * 100:.2f}%")
    print(classification_report(y_test, y_pred, target_names=class_names, digits=4))

# 6. Vẽ Hình 8: Biểu đồ so sánh Accuracy giữa 3 mô hình
print("\nĐang vẽ biểu đồ so sánh Accuracy...")
plt.figure(figsize=(8, 5))
palette = ['#4e79a7', '#59a14f', '#f28e2b']
bars = plt.bar(accuracies.keys(), [v * 100 for v in accuracies.values()], color=palette, width=0.5)

# Thêm nhãn giá trị phần trăm lên đầu mỗi cột
for bar in bars:
    yval = bar.get_height()
    plt.text(
        bar.get_x() + bar.get_width() / 2.0, 
        yval + 1, 
        f"{yval:.2f}%", 
        ha='center', 
        va='bottom', 
        fontsize=11, 
        weight='bold'
    )

plt.ylim(0, 100)
plt.title("Hình 8: Kết quả Accuracy trên 3 mô hình Decision Tree, Random Forest và XGBoost", fontsize=12, weight='bold')
plt.xlabel("Mô hình Học máy", fontsize=11)
plt.ylabel("Độ chính xác Accuracy (%)", fontsize=11)
plt.tight_layout()

os.makedirs("figures", exist_ok=True)
plt.savefig("figures/hinh_8_so_sanh_accuracy.png", dpi=300)
plt.close()
print(" -> Đã lưu biểu đồ vào: figures/hinh_8_so_sanh_accuracy.png")

# 7. Chọn mô hình tốt nhất và lưu lại
best_model_name = max(accuracies, key=accuracies.get)
best_model = trained_models[best_model_name]
joblib.dump(best_model, "best_student_model.pkl")
joblib.dump(le, "label_encoder.pkl")
print(f" -> Mô hình đạt hiệu suất cao nhất: {best_model_name} (Đã lưu file: best_student_model.pkl)")

# 8. Sinh tệp dự đoán kèm nhãn cảnh báo cho hệ thống Web
df_prediction = df.copy()
df_prediction['Predicted_Target'] = le.inverse_transform(best_model.predict(X))
# Gán cờ cảnh báo: Nếu dự đoán là Dropout -> Cần cảnh báo can thiệp học tập
df_prediction['Risk_Warning'] = df_prediction['Predicted_Target'].apply(
    lambda x: 'Cảnh báo nguy cơ thôi học' if x == 'Dropout' else 'Bình thường'
)
df_prediction.to_csv("student_predictions.csv", index=False)
print(" -> Đã xuất tệp 'student_predictions.csv' phục vụ cho hệ thống Dashboard.")

print("\n=== HOÀN TẤT CÔNG VIỆC NGÀY 4 ===")