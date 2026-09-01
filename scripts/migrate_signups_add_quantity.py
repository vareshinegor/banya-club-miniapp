"""Добавляет колонку "Количество" в лист «Записи» (сколько билетов куплено
одной записью), сохраняя все существующие записи. У старых строк проставляем
"1" — они все с тех времён, когда на одну запись был ровно один билет.

Запуск: .venv\\Scripts\\python.exe scripts\\migrate_signups_add_quantity.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from constants import SHEET_SIGNUPS, SIGNUPS_HEADERS
from sheets_client import get_worksheet


def main():
    ws = get_worksheet(SHEET_SIGNUPS)
    values = ws.get_all_values()
    if not values:
        print("Лист пуст, нечего мигрировать.")
        return

    old_headers = values[0]
    if "Количество" in old_headers:
        print("Колонка «Количество» уже есть, миграция не нужна.")
        return

    old_rows = values[1:]
    new_rows = []
    for row in old_rows:
        if not any(cell.strip() for cell in row):
            continue
        record = {old_headers[i]: (row[i] if i < len(row) else "") for i in range(len(old_headers))}
        record["Количество"] = "1"
        new_rows.append([record.get(h, "") for h in SIGNUPS_HEADERS])

    ws.clear()
    ws.update(range_name="A1", values=[SIGNUPS_HEADERS] + new_rows)
    print(f"Лист «{SHEET_SIGNUPS}» мигрирован, строк: {len(new_rows)}")
    for row in new_rows:
        print(" ", row)


if __name__ == "__main__":
    main()
