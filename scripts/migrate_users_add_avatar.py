"""Добавляет колонку "Аватарка" в лист «Пользователи» (ссылка на фото-аватар),
сохраняя данные уже прошедших анкету пользователей. У существующих строк
колонка остаётся пустой — заполняется автоматически при загрузке фото
(/api/upload-avatar, /api/admin/set-avatar) или при регистрации, если фото
уже было загружено на шаге анкеты.

Запуск: .venv\\Scripts\\python.exe scripts\\migrate_users_add_avatar.py
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
    if "Аватарка" in old_headers:
        print("Колонка «Аватарка» уже есть, миграция не нужна.")
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
