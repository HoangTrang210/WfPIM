# WfPIM Project

Dự án xử lý dữ liệu Employee từ PDF/CSV/JSON và đẩy dữ liệu vào SQL Server bằng FastAPI.

## Chức năng chính
- Đọc dữ liệu từ PDF
- Xuất ra JSON, CSV
- Xem dữ liệu qua API FastAPI
- Đẩy dữ liệu vào SQL Server

## Cấu trúc chính
- `employee_api 2.py`: API xử lý employee và upload SQL
- `gemini_parser.py`: parser dữ liệu từ PDF
- `main.py`: chạy xử lý chính
- `employee_db.sql`: script SQL

## Cách chạy
```bash
pip install -r requirements.txt
python employee_api 2.py