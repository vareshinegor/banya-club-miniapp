"""Расширяет лист «Пользователи» под новую анкету (Должность/Город/Телефон/Доход
+ новый порядок колонок), сохраняя данные уже прошедших анкету пользователей.
Новые поля у существующих строк остаются пустыми — они появятся у тех, кто
пройдёт анкету заново по обновлённому сценарию.

Запуск: .venv\\Scripts\\python.exe scripts\\migrate_users_schema_v2.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from constants import SHEET_USERS, USERS_HEADERS
from sheets_client import get_worksheet

# Тестовые/мусорные telegram_id, которые не нужно переносить.
DROP_IDS = {"900555111"}


def main():
    ws = get_worksheet(SHEET_USERS)
    values = ws.get_all_values()
    if not values:
        print("Лист пуст, нечего мигрировать.")
        return

    old_headers = values[0]
    old_rows = values[1:]

    new_rows = []
    for row in old_rows:
        if not any(cell.strip() for cell in row):
            continue
        record = {old_headers[i]: (row[i] if i < len(row) else "") for i in range(len(old_headers))}
        if record.get("telegram_id") in DROP_IDS:
            continue
        new_rows.append([record.get(h, "") for h in USERS_HEADERS])

    ws.clear()
    ws.update(range_name="A1", values=[USERS_HEADERS] + new_rows)
    print(f"Лист «{SHEET_USERS}» мигрирован, перенесено строк: {len(new_rows)}")
    for row in new_rows:
        print(" ", row)


if __name__ == "__main__":
    main()
