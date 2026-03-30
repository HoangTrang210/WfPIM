# WfPIM Project

WfPIM là dự án dùng để thu thập, chuyển đổi và quản lý dữ liệu nhân sự từ các tệp đầu vào như PDF, CSV, JSON. Hệ thống hỗ trợ xử lý dữ liệu bằng FastAPI, xuất dữ liệu sang nhiều định dạng và lưu vào SQL Server để phục vụ tra cứu và quản lý.

## Mục tiêu dự án
- Trích xuất dữ liệu Employee từ file đầu vào
- Chuyển đổi dữ liệu sang CSV và JSON
- Cung cấp API để xem và xử lý dữ liệu
- Lưu dữ liệu vào SQL Server

## Chức năng chính
- Đọc và phân tích dữ liệu từ file PDF
- Xuất dữ liệu sang định dạng CSV và JSON
- Hiển thị và xử lý dữ liệu thông qua FastAPI
- Tạo và lưu dữ liệu vào cơ sở dữ liệu SQL Server

## Cấu trúc thư mục chính
- `employee_api 2.py`: file chạy API FastAPI, hỗ trợ xử lý dữ liệu employee và lưu vào SQL Server
- `gemini_parser.py`: xử lý trích xuất dữ liệu từ file PDF
- `main.py`: file xử lý chính của chương trình
- `employee_db.sql`: script tạo database và bảng trong SQL Server
- `templates/`: chứa giao diện HTML
- `input/`: chứa file đầu vào
- `output/`: chứa file đầu ra CSV, JSON

## Yêu cầu môi trường
- Python 3.x
- SQL Server
- Các thư viện trong `requirements.txt`

## Cách cài đặt
Cài đặt các thư viện cần thiết:

```bash
pip install -r requirements.txt
python employee_api 2.py