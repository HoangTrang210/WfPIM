import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import create_engine  # MỚI: Để kết nối SQL
import uvicorn
import os
import io

app = FastAPI()

# --- CẤU HÌNH ---
FILE_PATH = r"C:/WfPIM/output/Employee_data_gan_1000.csv"
IMPORTANT_COLUMNS = [
    "Employee ID",
    "Age",
    "Gender",
    "Job Role",
    "Monthly Income",
    "Work-Life Balance",
    "Attrition",
]

# CẤU HÌNH SQL: Thay đổi User, Pass, Server và Database của bạn tại đây
# Định dạng: mssql+pyodbc://<user>:<pass>@<server>/<db>?driver=ODBC+Driver+17+for+SQL+Server
SQL_CONN_STR = (
    "mssql+pyodbc://.\\SQLEXPRESS/Employees_Processed"
    "?driver=ODBC+Driver+17+for+SQL+Server"
    "&trusted_connection=yes"
)
engine = create_engine(SQL_CONN_STR)

# --- HÀM HỖ TRỢ (HELPER FUNCTIONS) ---


def load_base_df():
    if not os.path.exists(FILE_PATH):
        return None
    return pd.read_csv(
        FILE_PATH, sep=None, encoding="utf-8-sig", on_bad_lines="skip", engine="python"
    )


def get_processed_df():
    df = load_base_df()
    if df is None:
        return None

    df.columns = df.columns.str.strip()
    existing_cols = [c for c in IMPORTANT_COLUMNS if c in df.columns]
    df_filtered = df[existing_cols].copy()

    df_top_10 = df_filtered.head(10).copy()
    if df_top_10.empty:
        return df_top_10

    df_final = pd.concat([df_top_10] * 100, ignore_index=True)

    if "Employee ID" in df_final.columns:
        df_final["Employee ID"] = range(10001, 10001 + len(df_final))

    return df_final.fillna("N/A")


# --- CÁC ĐƯỜNG DẪN (ENDPOINTS) ---


@app.get("/")
def home():
    return {
        "message": "Hệ thống quản lý dữ liệu Employee",
        "links": {
            "1. Xem JSON Gốc": "/data-raw",
            "2. Xem JSON Đã Xử lý": "/data-processed",
            "3. Tải CSV Gốc": "/download-raw",
            "4. Tải CSV Đã Xử lý": "/download-processed",
            "5. ĐẨY DỮ LIỆU VÀO SQL": "/upload-to-sql (POST)",
        },
    }


@app.get("/data-raw")
def get_data_raw():
    df = load_base_df()
    if df is not None:
        df = df.fillna("N/A")
        # Bước 1: Đảm bảo cột Employee ID không có giá trị trùng lặp
        # Nếu trùng, nó sẽ giữ lại dòng đầu tiên và xóa các dòng sau
        df_unique = df.drop_duplicates(subset=["Employee ID"])

        # Bước 2: Chuyển sang dictionary với ID làm Key
        return df_unique.set_index("Employee ID").to_dict(orient="index")
    else:
        return {"error": "File not found"}


@app.get("/data-processed")
def get_data_processed():
    df = get_processed_df()
    if df is not None:
        # Tương tự: đưa Employee ID ra làm khóa chính
        result = df.set_index("Employee ID").to_dict(orient="index")
        return result
    else:
        return {"error": "File not found"}


# MỚI: Endpoint đẩy dữ liệu vào SQL
@app.post("/upload-to-sql")
def upload_to_sql():
    df = load_base_df()
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="Không có dữ liệu để upload")

    try:
        # Làm sạch tên cột một lần nữa để SQL không lỗi (đổi khoảng trắng thành dấu gạch dưới)
        df.columns = [c.replace(" ", "_") for c in df.columns]

        # Đẩy dữ liệu vào bảng 'Employees_Processed'
        # if_exists='replace': Xóa bảng cũ nếu tồn tại và tạo bảng mới
        df.to_sql("Employees_Processed", con=engine, if_exists="replace", index=False)

        return {
            "status": "Thành công",
            "message": "Dữ liệu đã được đẩy vào SQL Server",
            "rows_uploaded": len(df),
            "table_name": "Employees_Processed",
        }
    except Exception as e:
        return {"status": "Thất bại", "error": str(e)}


@app.get("/download-raw")
def download_raw():
    df = load_base_df()
    if df is None:
        raise HTTPException(status_code=404, detail="File not found")
    stream = io.StringIO()
    df.to_csv(stream, index=False, encoding="utf-8-sig")
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=Employee_RAW.csv"},
    )


@app.get("/download-processed")
def download_processed():
    df = get_processed_df()
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="No data")
    stream = io.StringIO()
    df.to_csv(stream, index=False, encoding="utf-8-sig")
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=Employee_PROCESSED.csv"},
    )


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8088)
