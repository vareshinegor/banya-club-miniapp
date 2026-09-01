"""Добавляет колонку "Заказ" в лист «Записи» (для сопоставления с вебхуком
Продамуса), сохраняя все существующие записи. У старых строк "Заказ" остаётся
пустым — это ок, они уже оплачены по старой (мок) схеме.

Запуск: .venv\\Scripts\\python.exe scripts\\migrate_signups_add_order.py
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
    if "Заказ" in old_headers:
        print("Колонка «Заказ» уже есть, миграция не нужна.")
        return

    old_rows = values[1:]
    new_rows = []
    for row in old_rows:
        if not any(cell.strip() for cell in row):
            continue
        record = {old_headers[i]: (row[i] if i < len(row) else "") for i in range(len(old_headers))}
        new_rows.append([record.get(h, "") for h in SIGNUPS_HEADERS])

    ws.clear()
    ws.update(range_name="A1", values=[SIGNUPS_HEADERS] + new_rows)
    print(f"Лист «{SHEET_SIGNUPS}» мигрирован, строк: {len(new_rows)}")
    for row in new_rows:
        print(" ", row)


if __name__ == "__main__":
    main()
