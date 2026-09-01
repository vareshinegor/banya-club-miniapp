"""Добавляет колонку sb_id в лист «Пользователи» (для связки с сейлботом),
сохраняя данные уже прошедших анкету пользователей. У существующих строк
sb_id остаётся пустым — заполнится для тех, кто пройдёт анкету заново.

Запуск: .venv\\Scripts\\python.exe scripts\\migrate_users_add_sbid.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from constants import SHEET_USERS, USERS_HEADERS
from sheets_client import get_worksheet


def main():
    ws = get_worksheet(SHEET_USERS)
    values = ws.get_all_values()
    if not values:
        print("Лист пуст, нечего мигрировать.")
        return

    old_headers = values[0]
    if "sb_id" in old_headers:
        print("Колонка sb_id уже есть, миграция не нужна.")
        return

    old_rows = values[1:]
    new_rows = []
    for row in old_rows:
        if not any(cell.strip() for cell in row):
            continue
        record = {old_headers[i]: (row[i] if i < len(row) else "") for i in range(len(old_headers))}
        new_rows.append([record.get(h, "") for h in USERS_HEADERS])

    ws.clear()
    ws.update(range_name="A1", values=[USERS_HEADERS] + new_rows)
    print(f"Лист «{SHEET_USERS}» мигрирован, строк: {len(new_rows)}")
    for row in new_rows:
        print(" ", row)


if __name__ == "__main__":
    main()
