import json
import pandas as pd
import mysql.connector
from pymongo import MongoClient

# --- NẠP VÀO MYSQL (CỔNG 3307) ---
print("Đang nạp dữ liệu vào MySQL...")
cnx = mysql.connector.connect(
    host="127.0.0.1",
    port=3307,
    user="root",
    password="rootpassword",
    database="student_db"
)
cursor = cnx.cursor()

# Tạo bảng
cursor.execute("DROP TABLE IF EXISTS demographics")
cursor.execute("""
CREATE TABLE demographics (
    StudentID INT PRIMARY KEY,
    Marital_status INT,
    Nationality INT,
    Gender INT,
    Age_at_enrollment INT
)
""")

# Đọc file CSV và chèn dữ liệu
df_mysql = pd.read_csv('mysql_demographics.csv')
insert_query = """
INSERT INTO demographics (StudentID, Marital_status, Nationality, Gender, Age_at_enrollment)
VALUES (%s, %s, %s, %s, %s)
"""
for _, row in df_mysql.iterrows():
    cursor.execute(insert_query, tuple(row))

cnx.commit()
cursor.close()
cnx.close()
print("Hoàn tất nạp dữ liệu vào MySQL!")

# --- NẠP VÀO MONGODB ---
print("Đang nạp dữ liệu vào MongoDB...")
client = MongoClient("mongodb://127.0.0.1:27017/")
mongo_db = client["student_db"]
collection = mongo_db["student_behaviors"]

collection.drop()

with open('mongodb_behaviors.json', 'r') as f:
    mongo_docs = [json.loads(line) for line in f]

if mongo_docs:
    collection.insert_many(mongo_docs)

client.close()
print("Hoàn tất nạp dữ liệu vào MongoDB!")