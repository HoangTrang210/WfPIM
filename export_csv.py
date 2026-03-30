import csv
from pathlib import Path

from schema import ROW_KEYS


def export_rows_to_csv(rows, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=ROW_KEYS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, None) for key in ROW_KEYS})
