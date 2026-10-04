import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Tạo thư mục lưu ảnh biểu đồ cho báo cáo
os.makedirs("figures", exist_ok=True)

# 1. Đọc dữ liệu đã tích hợp
df = pd.read_csv("final_dataset.csv")

# Thiết lập phong cách hiển thị biểu đồ
sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.sans-serif': 'DejaVu Sans', 'font.size': 11})

# Định nghĩa chính xác tên các cột số cần phân tích
num_cols = [
    'Age_at_enrollment',
    'Curricular units 1st sem (grade)',
    'Curricular units 2nd sem (grade)'
]

col_titles = {
    'Age_at_enrollment': 'Độ tuổi nhập học (Age at enrollment)',
    'Curricular units 1st sem (grade)': 'Điểm số Học kỳ 1 (1st sem grade)',
    'Curricular units 2nd sem (grade)': 'Điểm số Học kỳ 2 (2nd sem grade)'
}

# ==========================================
# 1. VẼ CÁC BIỂU ĐỒ HISTOGRAM (Hình 1, Hình 2, Hình 3)
# ==========================================
print("Đang vẽ biểu đồ Histogram...")
for i, col in enumerate(num_cols, start=1):
    plt.figure(figsize=(8, 5))
    sns.histplot(df[col], kde=True, color='skyblue', bins=25)
    plt.title(f"Hình {i}: Biểu đồ Histogram cho biến {col}", fontsize=13, weight='bold')
    plt.xlabel(col_titles[col])
    plt.ylabel("Tần số (Frequency)")
    plt.tight_layout()
    plt.savefig(f"figures/hinh_{i}_histogram_{col.replace(' ', '_')}.png", dpi=300)
    plt.close()

# ==========================================
# 2. VẼ CÁC BIỂU ĐỒ BOXPLOT (Hình 4, Hình 5, Hình 6)
# ==========================================
print("Đang vẽ biểu đồ Boxplot theo nhóm Target...")
for i, col in enumerate(num_cols, start=4):
    plt.figure(figsize=(8, 5))
    sns.boxplot(x='Target', y=col, data=df, hue='Target', palette='Set2', legend=False)
    plt.title(f"Hình {i}: Biểu đồ Boxplot cho biến {col} theo Target", fontsize=13, weight='bold')
    plt.xlabel("Trạng thái học tập (Target)")
    plt.ylabel(col_titles[col])
    plt.tight_layout()
    plt.savefig(f"figures/hinh_{i}_boxplot_{col.replace(' ', '_')}.png", dpi=300)
    plt.close()

# ==========================================
# 3. VẼ BIỂU ĐỒ HEATMAP TƯƠNG QUAN (Hình 7)
# ==========================================
print("Đang vẽ biểu đồ Heatmap ma trận tương quan...")
plt.figure(figsize=(10, 8))

# Chọn các cột số để tính tương quan ma trận Pearson
numeric_df = df.select_dtypes(include=['int64', 'float64']).drop(columns=['StudentID'], errors='ignore')
corr_matrix = numeric_df.corr()

sns.heatmap(
    corr_matrix, 
    annot=True, 
    fmt=".2f", 
    cmap="coolwarm", 
    cbar=True,
    linewidths=0.5
)
plt.title("Hình 7: Biểu đồ Heatmap ma trận tương quan giữa các biến", fontsize=14, weight='bold')
plt.tight_layout()
plt.savefig("figures/hinh_7_heatmap_correlation.png", dpi=300)
plt.close()

print("\nHoàn tất! Toàn bộ 7 hình ảnh đã được lưu vào thư mục 'figures/'.")