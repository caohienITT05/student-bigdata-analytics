import pandas as pd
import mysql.connector
from pymongo import MongoClient

print("=== BẮT ĐẦU LUỒNG TÍCH HỢP DỮ LIỆU (ETL) ===")

# ==========================================
# 1. EXTRACT: Trích xuất từ 3 nguồn độc lập
# ==========================================
print("\n[1/3] Trích xuất dữ liệu...")

# 1.1 Trích xuất từ MySQL
try:
    cnx = mysql.connector.connect(
        host="127.0.0.1",
        port=3307,
        user="root",
        password="rootpassword",
        database="student_db"
    )
    query = "SELECT * FROM demographics"
    df_mysql = pd.read_sql(query, cnx)
    cnx.close()
    print(f" -> Trích xuất MySQL thành công: {df_mysql.shape[0]} dòng, {df_mysql.shape[1]} cột")
except Exception as e:
    print(f"Lỗi khi trích xuất MySQL: {e}")

# 1.2 Trích xuất từ MongoDB
try:
    client = MongoClient("mongodb://127.0.0.1:27017/")
    db = client["student_db"]
    collection = db["student_behaviors"]
    # Bỏ trường _id mặc định của Mongo
    mongo_data = list(collection.find({}, {"_id": 0}))
    df_mongo = pd.DataFrame(mongo_data)
    client.close()
    print(f" -> Trích xuất MongoDB thành công: {df_mongo.shape[0]} dòng, {df_mongo.shape[1]} cột")
except Exception as e:
    print(f"Lỗi khi trích xuất MongoDB: {e}")

# 1.3 Trích xuất từ File phẳng (CSV)
try:
    df_csv = pd.read_csv("flat_grades.csv")
    print(f" -> Đọc file flat_grades.csv thành công: {df_csv.shape[0]} dòng, {df_csv.shape[1]} cột")
except Exception as e:
    print(f"Lỗi khi đọc file flat_grades.csv: {e}")


# ==========================================
# 2. TRANSFORM: Hợp nhất và Làm sạch dữ liệu
# ==========================================
print("\n[2/3] Hợp nhất và biến đổi dữ liệu (Transform)...")

# 2.1 Hợp nhất 3 nguồn theo khóa chính StudentID
df_merged = df_mysql.merge(df_mongo, on="StudentID", how="inner")
df_final = df_merged.merge(df_csv, on="StudentID", how="inner")
print(f" -> Dữ liệu sau khi JOIN 3 nguồn: {df_final.shape[0]} dòng, {df_final.shape[1]} cột")

# 2.2 Kiểm tra và xử lý giá trị bị thiếu (Missing values)
null_counts = df_final.isnull().sum().sum()
print(f" -> Số lượng giá trị thiếu (Null values): {null_counts}")
if null_counts > 0:
    # Điền giá trị trung vị cho cột số nếu có giá trị rỗng
    df_final.fillna(df_final.median(numeric_only=True), inplace=True)
    print(" -> Đã làm sạch và bù đắp các giá trị trống.")

# 2.3 Xem qua 3 dòng đầu tiên của dữ liệu hợp nhất
print("\nBảng dữ liệu tích hợp mẫu:")
print(df_final.head(3))


# ==========================================
# 3. LOAD: Lưu vào Kho dữ liệu tập trung
# ==========================================
print("\n[3/3] Tải dữ liệu vào Kho lưu trữ tập trung (Load)...")
output_path = "final_dataset.csv"
df_final.to_csv(output_path, index=False)
print(f" -> Đã lưu thành công tập dữ liệu sạch vào '{output_path}'")

print("\n=== HOÀN TẤT QUÁ TRÌNH TÍCH HỢP DỮ LIỆU (ETL) ===")