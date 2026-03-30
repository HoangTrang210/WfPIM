import json
import os
import re
import time
from collections import OrderedDict
from pathlib import Path

import fitz
from dotenv import load_dotenv

from schema import ROW_KEYS, ROWS_SCHEMA

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "5"))
RECORDS_PER_BLOCK = int(os.getenv("RECORDS_PER_BLOCK", "10"))
BLOCK_SLEEP_SECONDS = float(os.getenv("BLOCK_SLEEP_SECONDS", "1.5"))
USE_GEMINI_FALLBACK = os.getenv("USE_GEMINI_FALLBACK", "0") == "1"

_client = None
_types = None

HEADER_PREFIXES = (
    "Employee I",
    "Employee ID",
    "Gender",
    "Years at Co",
    "Monthly In",
    "Distance fro",
    "Company S",
)

EDUCATION_PATTERNS = [
    (re.compile(r"Associate\s*D", re.IGNORECASE), "Associate Degree"),
    (re.compile(r"High\s*Schoo\w*", re.IGNORECASE), "High School"),
    (re.compile(r"Bachelor(?:'s)?(?:\s+Degree)?", re.IGNORECASE), "Bachelor's Degree"),
    (re.compile(r"Master(?:'s)?(?:\s+Degree)?", re.IGNORECASE), "Master's Degree"),
    (re.compile(r"PhD", re.IGNORECASE), "PhD"),
]

MARITAL_VALUES = ["Single", "Married", "Divorced"]
JOB_LEVEL_VALUES = ["Entry", "Mid", "Senior"]
COMPANY_SIZE_VALUES = ["Small", "Medium", "Large"]
YN_VALUES = ["Yes", "No"]
ATTRITION_VALUES = ["Stayed", "Left"]
LEVEL_VALUES = [
    "Very High",
    "High",
    "Medium",
    "Low",
    "Excellent",
    "Good",
    "Fair",
    "Poor",
    "Average",
]
INT_FIELDS = {
    "employee_id",
    "age",
    "years_at_company",
    "monthly_income",
    "number_of_promotions",
    "distance_from_home",
    "number_of_dependents",
    "company_tenure_in_months",
}


class ParseError(Exception):
    pass


def _ensure_gemini():
    global _client, _types
    if _client is not None:
        return _client, _types

    if not API_KEY:
        raise ValueError("Thiếu GEMINI_API_KEY trong file .env")

    from google import genai
    from google.genai import types

    _client = genai.Client(api_key=API_KEY)
    _types = types
    return _client, _types


def normalize_text(text: str) -> str:
    text = text.replace("â€™", "'").replace("â€", "'").replace("’", "'")
    text = " ".join(text.strip().split())
    return text


def empty_row():
    return OrderedDict((key, None) for key in ROW_KEYS)


def safe_int(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip().replace(",", "")
    return int(s) if s.isdigit() else None


def normalize_choice(text: str, allowed_values):
    if text is None:
        return None
    s = normalize_text(str(text))
    for value in allowed_values:
        if s.lower() == value.lower():
            return value
    return None


def find_first_allowed(text: str, allowed_values):
    if not text:
        return None
    s = normalize_text(text)
    for value in allowed_values:
        if re.search(rf"\b{re.escape(value)}\b", s, re.IGNORECASE):
            return value
    return None


def normalize_education(text: str):
    if not text:
        return None
    s = normalize_text(text)
    for pattern, replacement in EDUCATION_PATTERNS:
        if pattern.search(s):
            return replacement
    return s if s else None


def extract_education_and_marital(text: str):
    s = normalize_text(text)
    if not s:
        return None, None

    s = s.replace("Bachelor's", "Bachelor").replace("Master's", "Master")

    marital = None
    for value in MARITAL_VALUES:
        if re.search(rf"{value}$", s, re.IGNORECASE):
            marital = value
            s = re.sub(rf"{value}$", "", s, flags=re.IGNORECASE).strip()
            break

    if marital is None:
        for value in MARITAL_VALUES:
            if re.search(rf"\b{value}\b", s, re.IGNORECASE):
                marital = value
                s = re.sub(rf"\b{value}\b", "", s, flags=re.IGNORECASE).strip()
                break

    education = normalize_education(s) if s else None
    return education, marital


def read_pdf_lines(pdf_path: str):
    pdf_path = str(Path(pdf_path))
    doc = fitz.open(pdf_path)
    raw_lines = []
    try:
        for page in doc:
            text = page.get_text("text")
            if not text:
                continue
            for line in text.splitlines():
                s = normalize_text(line)
                if not s:
                    continue
                if s.startswith(HEADER_PREFIXES):
                    continue
                if re.fullmatch(r"\d+\s*/\s*\d+", s):
                    continue
                raw_lines.append(s)
    finally:
        doc.close()
    return raw_lines


def is_record_start(lines, i: int) -> bool:
    if i + 1 >= len(lines):
        return False
    return bool(
        re.fullmatch(r"\d{1,10}", lines[i])
        and re.fullmatch(r"\d{1,3}\s+(Male|Female)", lines[i + 1])
    )


def split_raw_records(lines):
    starts = [i for i in range(len(lines)) if is_record_start(lines, i)]
    records = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        record = lines[start:end]
        if record:
            records.append(record)
    return records


def parse_age_gender(line: str):
    m = re.fullmatch(r"(\d{1,3})\s+(Male|Female)", normalize_text(line))
    if not m:
        raise ParseError(f"Không parse được age/gender: {line}")
    return int(m.group(1)), m.group(2)


def parse_years_job(line: str):
    m = re.fullmatch(r"(\d+)\s+(.+)", normalize_text(line))
    if not m:
        raise ParseError(f"Không parse được years_at_company/job_role: {line}")
    return int(m.group(1)), m.group(2).strip()


def parse_int_last_token(line: str):
    m = re.fullmatch(r"(\d+)\s+(.+)", normalize_text(line))
    if not m:
        raise ParseError(f"Không parse được line số + text: {line}")
    return int(m.group(1)), m.group(2).strip()


def parse_int_bool(line: str):
    m = re.fullmatch(r"(\d+)\s+(Yes|No)", normalize_text(line))
    if not m:
        raise ParseError(f"Không parse được line số + yes/no: {line}")
    return int(m.group(1)), m.group(2)


def parse_level_tokens(text: str):
    text = normalize_text(text)
    tokens = []
    while text:
        matched = False
        for value in LEVEL_VALUES:
            if text == value:
                tokens.append(value)
                text = ""
                matched = True
                break
            if text.startswith(value + " "):
                tokens.append(value)
                text = text[len(value):].strip()
                matched = True
                break
        if not matched:
            break
    return tokens, text


def parse_record_locally(record_lines):
    if len(record_lines) < 14:
        raise ParseError(f"Record quá ngắn: {record_lines}")

    row = empty_row()

    row["employee_id"] = safe_int(record_lines[0])
    row["age"], row["gender"] = parse_age_gender(record_lines[1])
    row["years_at_company"], row["job_role"] = parse_years_job(record_lines[2])
    row["monthly_income"], rest = parse_int_last_token(record_lines[3])

    vals, _ = parse_level_tokens(rest)
    if vals:
        row["work_life_balance"] = vals[0]
        if len(vals) > 1:
            row["job_satisfaction"] = vals[1]
    else:
        row["work_life_balance"] = normalize_choice(rest, LEVEL_VALUES) or rest

    idx = 4
    if row["job_satisfaction"] is None:
        vals, _ = parse_level_tokens(record_lines[idx])
        if vals:
            row["job_satisfaction"] = vals[0]
            if len(vals) > 1:
                row["performance_rating"] = vals[1]
        else:
            row["job_satisfaction"] = normalize_choice(record_lines[idx], LEVEL_VALUES) or record_lines[idx]
        idx += 1

    if row["performance_rating"] is None:
        row["performance_rating"] = normalize_choice(record_lines[idx], LEVEL_VALUES) or record_lines[idx]
        idx += 1

    row["number_of_promotions"], row["overtime"] = parse_int_bool(record_lines[idx])
    idx += 1

    distance, rest = parse_int_last_token(record_lines[idx])
    row["distance_from_home"] = distance
    row["education_level"], row["marital_status"] = extract_education_and_marital(rest)
    idx += 1

    row["number_of_dependents"], job_level_raw = parse_int_last_token(record_lines[idx])
    row["job_level"] = normalize_choice(job_level_raw, JOB_LEVEL_VALUES) or job_level_raw
    idx += 1

    row["company_size"] = normalize_choice(record_lines[idx], COMPANY_SIZE_VALUES) or record_lines[idx]
    idx += 1

    row["company_tenure_in_months"], row["remote_work"] = parse_int_bool(record_lines[idx])
    idx += 1

    row["leadership_opportunities"] = normalize_choice(record_lines[idx], YN_VALUES) or record_lines[idx]
    idx += 1
    row["innovation_opportunities"] = normalize_choice(record_lines[idx], YN_VALUES) or record_lines[idx]
    idx += 1
    row["company_reputation"] = normalize_choice(record_lines[idx], LEVEL_VALUES) or record_lines[idx]
    idx += 1
    row["employee_recognition"] = normalize_choice(record_lines[idx], YN_VALUES) or record_lines[idx]
    idx += 1
    row["attrition"] = normalize_choice(record_lines[idx], ATTRITION_VALUES) or record_lines[idx]

    return row


def fallback_parse_record_locally(record_lines):
    row = empty_row()
    lines = [normalize_text(x) for x in record_lines if normalize_text(x)]

    if not lines:
        return row

    row["employee_id"] = safe_int(lines[0]) if re.fullmatch(r"\d{1,10}", lines[0]) else None

    if len(lines) > 1:
        m = re.fullmatch(r"(\d{1,3})\s+(Male|Female)", lines[1])
        if m:
            row["age"] = int(m.group(1))
            row["gender"] = m.group(2)

    if len(lines) > 2:
        m = re.fullmatch(r"(\d+)\s+(.+)", lines[2])
        if m:
            row["years_at_company"] = int(m.group(1))
            row["job_role"] = m.group(2).strip()

    if len(lines) > 3:
        m = re.fullmatch(r"(\d+)\s+(.+)", lines[3])
        if m:
            row["monthly_income"] = int(m.group(1))
            rest = m.group(2).strip()
            vals, leftover = parse_level_tokens(rest)
            if vals:
                row["work_life_balance"] = vals[0]
                if len(vals) > 1:
                    row["job_satisfaction"] = vals[1]
            elif normalize_choice(rest, LEVEL_VALUES):
                row["work_life_balance"] = normalize_choice(rest, LEVEL_VALUES)
            elif leftover:
                row["work_life_balance"] = leftover

    level_candidates = []
    yn_candidates = []
    attrition_candidate = None
    company_size_candidate = None
    edu_candidate = None
    marital_candidate = None

    for line in lines[4:]:
        if row["performance_rating"] is None:
            lv = normalize_choice(line, LEVEL_VALUES)
            if lv:
                level_candidates.append(lv)
                continue

        if row["number_of_promotions"] is None:
            m = re.fullmatch(r"(\d+)\s+(Yes|No)", line)
            if m:
                row["number_of_promotions"] = int(m.group(1))
                row["overtime"] = m.group(2)
                continue

        if row["distance_from_home"] is None:
            m = re.fullmatch(r"(\d+)\s+(.+)", line)
            if m:
                maybe_num = int(m.group(1))
                maybe_text = m.group(2).strip()
                edu, marital = extract_education_and_marital(maybe_text)
                if edu or marital:
                    row["distance_from_home"] = maybe_num
                    edu_candidate = edu
                    marital_candidate = marital
                    continue

        if row["number_of_dependents"] is None:
            m = re.fullmatch(r"(\d+)\s+(.+)", line)
            if m:
                maybe_num = int(m.group(1))
                maybe_text = m.group(2).strip()
                jl = normalize_choice(maybe_text, JOB_LEVEL_VALUES)
                if jl:
                    row["number_of_dependents"] = maybe_num
                    row["job_level"] = jl
                    continue

        if company_size_candidate is None:
            cs = normalize_choice(line, COMPANY_SIZE_VALUES)
            if cs:
                company_size_candidate = cs
                continue

        if row["company_tenure_in_months"] is None:
            m = re.fullmatch(r"(\d+)\s+(Yes|No)", line)
            if m:
                row["company_tenure_in_months"] = int(m.group(1))
                row["remote_work"] = m.group(2)
                continue

        yn = normalize_choice(line, YN_VALUES)
        if yn:
            yn_candidates.append(yn)
            continue

        attr = normalize_choice(line, ATTRITION_VALUES)
        if attr:
            attrition_candidate = attr
            continue

        lv = normalize_choice(line, LEVEL_VALUES)
        if lv:
            level_candidates.append(lv)

    if row["job_satisfaction"] is None and level_candidates:
        row["job_satisfaction"] = level_candidates.pop(0)

    if row["performance_rating"] is None and level_candidates:
        row["performance_rating"] = level_candidates.pop(0)

    if edu_candidate is not None:
        row["education_level"] = edu_candidate
    if marital_candidate is not None:
        row["marital_status"] = marital_candidate
    if company_size_candidate is not None:
        row["company_size"] = company_size_candidate

    if row["leadership_opportunities"] is None and yn_candidates:
        row["leadership_opportunities"] = yn_candidates.pop(0)
    if row["innovation_opportunities"] is None and yn_candidates:
        row["innovation_opportunities"] = yn_candidates.pop(0)
    if row["employee_recognition"] is None and yn_candidates:
        row["employee_recognition"] = yn_candidates.pop(0)

    if row["company_reputation"] is None and level_candidates:
        row["company_reputation"] = level_candidates.pop(0)

    if attrition_candidate is not None:
        row["attrition"] = attrition_candidate

    return row


def parse_records_locally(record_lines_list, limit_rows: int):
    rows = []
    errors = []

    selected = record_lines_list[:limit_rows]
    for rec in selected:
        try:
            row = parse_record_locally(rec)
            rows.append(row)
        except Exception as exc:
            fallback_row = fallback_parse_record_locally(rec)
            if fallback_row.get("employee_id") is not None:
                rows.append(fallback_row)
            errors.append({
                "employee_id": rec[0] if rec else None,
                "error": str(exc),
                "record": rec,
                "fallback_used": True,
            })

    return rows, errors


def _parse_retry_delay(message: str) -> int:
    match = re.search(r"retry in\s+(\d+(?:\.\d+)?)s", message, re.IGNORECASE)
    if match:
        return max(1, int(float(match.group(1))) + 1)
    match = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+)s", message, re.IGNORECASE)
    if match:
        return max(1, int(match.group(1)) + 1)
    return 15


def build_prompt(records_text: str, expected_count: int) -> str:
    return f'''Bạn đang trích xuất dữ liệu nhân viên từ văn bản PDF đã được làm sạch.

Nhiệm vụ:
- Trích xuất đúng {expected_count} record theo đúng thứ tự xuất hiện.
- Mỗi record bắt đầu từ employee_id.
- Không bỏ record.
- Không đảo thứ tự record.
- Không đổi tên key.
- Không thêm key mới.
- Nếu không chắc giá trị thì để null.
- Chỉ trả JSON hợp lệ.

Thứ tự key bắt buộc trong mọi object:
{json.dumps(ROW_KEYS, ensure_ascii=False)}

Văn bản nguồn:
"""
{records_text}
"""'''


def call_gemini_with_retry(prompt: str):
    client, types = _ensure_gemini()
    attempt = 0
    while True:
        try:
            return client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    response_json_schema=ROWS_SCHEMA,
                ),
            )
        except Exception as exc:
            message = str(exc)
            is_quota = "429" in message or "RESOURCE_EXHAUSTED" in message
            if not is_quota:
                raise
            attempt += 1
            if attempt > MAX_RETRIES:
                raise RuntimeError(f"Vượt quota sau {MAX_RETRIES} lần thử lại:\n{message}") from exc
            wait_seconds = _parse_retry_delay(message)
            print(f"Quota tạm thời bị vượt. Chờ {wait_seconds}s rồi thử lại ({attempt}/{MAX_RETRIES})...")
            time.sleep(wait_seconds)


def postprocess_rows(rows):
    fixed_rows = []
    for row in rows:
        ordered = OrderedDict((key, row.get(key, None)) for key in ROW_KEYS)

        for field in INT_FIELDS:
            ordered[field] = safe_int(ordered[field])

        ordered["gender"] = normalize_choice(ordered.get("gender"), ["Male", "Female"])
        ordered["overtime"] = normalize_choice(ordered.get("overtime"), YN_VALUES)
        ordered["remote_work"] = normalize_choice(ordered.get("remote_work"), YN_VALUES)
        ordered["leadership_opportunities"] = normalize_choice(ordered.get("leadership_opportunities"), YN_VALUES)
        ordered["innovation_opportunities"] = normalize_choice(ordered.get("innovation_opportunities"), YN_VALUES)
        ordered["employee_recognition"] = normalize_choice(ordered.get("employee_recognition"), YN_VALUES)
        ordered["job_level"] = normalize_choice(ordered.get("job_level"), JOB_LEVEL_VALUES)
        ordered["company_size"] = normalize_choice(ordered.get("company_size"), COMPANY_SIZE_VALUES)
        ordered["attrition"] = normalize_choice(ordered.get("attrition"), ATTRITION_VALUES)

        for field in ["work_life_balance", "job_satisfaction", "performance_rating", "company_reputation"]:
            ordered[field] = normalize_choice(ordered.get(field), LEVEL_VALUES) or ordered.get(field)

        ordered["education_level"] = normalize_education(ordered.get("education_level"))
        fixed_rows.append(ordered)

    return fixed_rows


def extract_rows_with_gemini(record_lines_list, limit_rows: int):
    selected = record_lines_list[:limit_rows]
    all_rows = []
    total_chunks = (len(selected) + RECORDS_PER_BLOCK - 1) // RECORDS_PER_BLOCK

    for idx in range(0, len(selected), RECORDS_PER_BLOCK):
        chunk = selected[idx:idx + RECORDS_PER_BLOCK]
        expected_count = len(chunk)
        prompt = build_prompt("\n".join(" ".join(r) for r in chunk), expected_count)
        block_no = idx // RECORDS_PER_BLOCK + 1
        print(f"Đang xử lý block Gemini {block_no}/{total_chunks} ({expected_count} record)...")
        response = call_gemini_with_retry(prompt)
        text = (response.text or "").strip()
        if not text:
            raise ValueError(f"Gemini không trả dữ liệu ở block {block_no}")
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError(f"Block {block_no} không trả về list JSON")
        all_rows.extend(postprocess_rows(data))
        if block_no < total_chunks:
            time.sleep(BLOCK_SLEEP_SECONDS)

    return all_rows


def extract_rows_from_pdf(pdf_path: str, limit_rows: int):
    if limit_rows <= 0:
        raise ValueError("limit_rows phải > 0")

    lines = read_pdf_lines(pdf_path)
    record_lines_list = split_raw_records(lines)
    if not record_lines_list:
        raise ValueError("Không tách được record nào từ PDF")

    expected = min(limit_rows, len(record_lines_list))
    local_rows, local_errors = parse_records_locally(record_lines_list, limit_rows)
    local_rows = postprocess_rows(local_rows)

    if len(local_rows) >= expected:
        return local_rows[:expected]

    print(f"Parser cục bộ parse được {len(local_rows)}/{expected} record.")
    if local_errors:
        print("3 lỗi đầu tiên của parser cục bộ:")
        for err in local_errors[:3]:
            print(err)

    if not USE_GEMINI_FALLBACK:
        if local_rows:
            return local_rows
        raise ValueError("Không parse được record nào từ PDF bằng parser cục bộ")

    if not API_KEY:
        if local_rows:
            return local_rows
        raise ValueError("Không parse được record nào từ PDF và chưa có GEMINI_API_KEY để fallback")

    gemini_rows = extract_rows_with_gemini(record_lines_list, limit_rows)
    gemini_rows = postprocess_rows(gemini_rows)

    if gemini_rows:
        return gemini_rows[:expected]

    if local_rows:
        return local_rows[:expected]

    raise ValueError("Không trích xuất được dữ liệu từ PDF")