from schema import ROW_KEYS

VALID_GENDER = {"Male", "Female"}
VALID_YN = {"Yes", "No"}
VALID_ATTRITION = {"Stayed", "Left"}
VALID_JOB_LEVEL = {"Entry", "Mid", "Senior"}
VALID_COMPANY_SIZE = {"Small", "Medium", "Large"}

INTEGER_FIELDS = {
    "employee_id",
    "age",
    "years_at_company",
    "monthly_income",
    "number_of_promotions",
    "distance_from_home",
    "number_of_dependents",
    "company_tenure_in_months",
}


def validate_rows(rows):
    errors = []

    for i, row in enumerate(rows, start=1):
        if list(row.keys()) != ROW_KEYS:
            errors.append({"row": i, "type": "wrong_key_order"})

        for key in ROW_KEYS:
            if key not in row:
                errors.append({"row": i, "type": "missing_key", "field": key})

        for field in INTEGER_FIELDS:
            value = row.get(field)
            if value is not None and not isinstance(value, int):
                errors.append({"row": i, "type": "invalid_int", "field": field, "value": value})

        if row.get("gender") not in VALID_GENDER and row.get("gender") is not None:
            errors.append({"row": i, "type": "invalid_gender", "value": row.get("gender")})

        for field in ["overtime", "remote_work", "leadership_opportunities", "innovation_opportunities"]:
            if row.get(field) not in VALID_YN and row.get(field) is not None:
                errors.append({"row": i, "type": "invalid_yes_no", "field": field, "value": row.get(field)})

        if row.get("attrition") not in VALID_ATTRITION and row.get("attrition") is not None:
            errors.append({"row": i, "type": "invalid_attrition", "value": row.get("attrition")})

        if row.get("job_level") not in VALID_JOB_LEVEL and row.get("job_level") is not None:
            errors.append({"row": i, "type": "invalid_job_level", "value": row.get("job_level")})

        if row.get("company_size") not in VALID_COMPANY_SIZE and row.get("company_size") is not None:
            errors.append({"row": i, "type": "invalid_company_size", "value": row.get("company_size")})

        if row.get("employee_id") is None or not isinstance(row.get("employee_id"), int):
            errors.append({"row": i, "type": "invalid_employee_id", "value": row.get("employee_id")})

    return errors


def summarize_errors(errors):
    if not errors:
        return {"total_errors": 0}

    summary = {}
    for err in errors:
        err_type = err["type"]
        summary[err_type] = summary.get(err_type, 0) + 1

    return {"total_errors": len(errors), "by_type": summary}
