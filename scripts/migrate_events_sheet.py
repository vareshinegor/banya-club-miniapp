"""Добавляет колонку ID в лист «Афиша», сохраняя текущие номера строк как ID
(строка 2 -> ID "2", строка 3 -> ID "3", ...), чтобы уже существующие записи
в листе «Записи» (которые ссылаются на старые row-based ID) не сломались.

Запуск: .venv\\Scripts\\python.exe scripts\\migrate_events_sheet.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from constants import EVENTS_HEADERS, SHEET_EVENTS
from sheets_client import get_worksheet


def main():
    ws = get_worksheet(SHEET_EVENTS)
    values = ws.get_all_values()
    if not values:
        print("Лист пуст, нечего мигрировать.")
        return

    old_headers = values[0]
    if old_headers and old_headers[0] == "ID":
        print("Колонка ID уже есть, миграция не нужна.")
        return

    data_rows = values[1:]
    width = len(old_headers)

    new_rows = []
    for i, row in enumerate(data_rows, start=2):
        if not any(cell.strip() for cell in row):
            continue
        padded = row + [""] * (width - len(row))
        new_rows.append([str(i)] + padded)

    ws.clear()
    ws.update(range_name="A1", values=[EVENTS_HEADERS] + new_rows)
    print(f"Лист «{SHEET_EVENTS}» мигрирован, {len(new_rows)} событий(ия):")
    for row in new_rows:
        print(" ", row)


if __name__ == "__main__":
    main()
