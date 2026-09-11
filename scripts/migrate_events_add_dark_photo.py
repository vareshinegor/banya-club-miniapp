"""Добавляет колонку "Фото темное" в лист «Афиша» (отдельная затемнённая
обложка для карточки "Ближайшее событие" на Главной), сохраняя все
существующие события. У всех событий она остаётся пустой — пустая
"Фото темное" означает "использовать обычное Фото" (см. _public_event в
routes.py).

Запуск: .venv\\Scripts\\python.exe scripts\\migrate_events_add_dark_photo.py
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
    if "Фото темное" in old_headers:
        print("Колонка «Фото темное» уже есть, миграция не нужна.")
        return

    old_rows = values[1:]
    new_rows = []
    for row in old_rows:
        if not any(cell.strip() for cell in row):
            continue
        record = {old_headers[i]: (row[i] if i < len(row) else "") for i in range(len(old_headers))}
        new_rows.append([record.get(h, "") for h in EVENTS_HEADERS])

    ws.clear()
    ws.update(range_name="A1", values=[EVENTS_HEADERS] + new_rows)
    print(f"Лист «{SHEET_EVENTS}» мигрирован, строк: {len(new_rows)}")
    for row in new_rows:
        print(" ", row)


if __name__ == "__main__":
    main()
