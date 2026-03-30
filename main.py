from pathlib import Path
import json

from export_csv import export_rows_to_csv
from gemini_parser import extract_rows_from_pdf
from validator import summarize_errors, validate_rows

BASE_DIR = Path(__file__).resolve().parent
PDF_PATH = BASE_DIR / "input" / "Employee_data.pdf"
OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_LIMIT_ROWS = 10


def save_json(data, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run_case(limit_rows: int, json_name: str, csv_name: str):
    rows = extract_rows_from_pdf(str(PDF_PATH), limit_rows)
    errors = validate_rows(rows)

    json_path = OUTPUT_DIR / json_name
    csv_path = OUTPUT_DIR / csv_name

    save_json(rows, json_path)
    export_rows_to_csv(rows, csv_path)

    print(f"Requested : {limit_rows}")
    print(f"Extracted : {len(rows)}")
    print(f"JSON saved: {json_path}")
    print(f"CSV saved : {csv_path}")

    if errors:
        print("Validation summary:", summarize_errors(errors))
        print("First 10 errors:")
        for error in errors[:10]:
            print(error)
    else:
        print("validate ok")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not PDF_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy file PDF: {PDF_PATH}")

    run_case(10, "Employee_data_10.json", "Employee_data_10.csv")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(type(e).__name__, ":", e)