"""Добавляет колонку "Фото" в лист «Материалы» (обложка карточки материала),
сохраняя уже добавленные материалы. У существующих строк остаётся пустой —
карточка просто не покажет обложку, как и раньше.

Запуск: .venv\\Scripts\\python.exe scripts\\migrate_materials_add_photo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from constants import MATERIALS_HEADERS, SHEET_MATERIALS
from sheets_client import get_worksheet


def main():
    ws = get_worksheet(SHEET_MATERIALS)
    values = ws.get_all_values()
    if not values:
        print("Лист пуст, нечего мигрировать.")
        return

    old_headers = values[0]
    if "Фото" in old_headers:
        print("Колонка «Фото» уже есть, миграция не нужна.")
        return

    old_rows = values[1:]
    new_rows = []
    for row in old_rows:
        if not any(cell.strip() for cell in row):
            continue
        record = {old_headers[i]: (row[i] if i < len(row) else "") for i in range(len(old_headers))}
        new_rows.append([record.get(h, "") for h in MATERIALS_HEADERS])

    ws.clear()
    ws.update(range_name="A1", values=[MATERIALS_HEADERS] + new_rows)
    print(f"Лист «{SHEET_MATERIALS}» мигрирован, строк: {len(new_rows)}")
    for row in new_rows:
        print(" ", row)


if __name__ == "__main__":
    main()
