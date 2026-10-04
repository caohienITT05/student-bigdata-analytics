import pandas as pd

# 1. Đọc file dataset.csv (tự động kiểm tra phân cách chấm phẩy hoặc phẩy)
try:
    df = pd.read_csv('dataset.csv', sep=';')
    if len(df.columns) <= 1:
        df = pd.read_csv('dataset.csv', sep=',')
except Exception:
    df = pd.read_csv('dataset.csv', sep=',')

# 2. Tạo mã sinh viên giả lập để làm khóa chính (Primary Key)
df['StudentID'] = range(23010001, 23010001 + len(df))

# 3. Nguồn 1: Nhân khẩu học (Lưu cho MySQL)
# Lấy cột gốc 'Nacionality' (chữ 'c') rồi đổi tên thành 'Nationality' (chữ 't')
demographics = df[['StudentID', 'Marital status', 'Nacionality', 'Gender', 'Age at enrollment']].copy()
demographics.rename(columns={'Nacionality': 'Nationality'}, inplace=True)
demographics.to_csv('mysql_demographics.csv', index=False)

# 4. Nguồn 2: Hành vi và nghĩa vụ học phí (Lưu cho MongoDB)
behaviors = df[['StudentID', 'Debtor', 'Tuition fees up to date', 'Scholarship holder']].copy()
behaviors.to_json('mongodb_behaviors.json', orient='records', lines=True)

# 5. Nguồn 3: Điểm số các kỳ và kết quả (Lưu file phẳng CSV)
grades = df[['StudentID', 'Curricular units 1st sem (grade)', 'Curricular units 2nd sem (grade)', 'Target']].copy()
grades.to_csv('flat_grades.csv', index=False)

print("Đã tách thành công thành 3 file:")
print("- mysql_demographics.csv")
print("- mongodb_behaviors.json")
print("- flat_grades.csv")