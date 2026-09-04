"""Переводит лист «Пользователи» с двух статусов ("активный"/"неактивный") на
три ("резидент"/"нерезидент"/"на рассмотрении"):

  активный    -> резидент          (анкета одобрена, подписка оплачена)
  неактивный  -> на рассмотрении   (в старой системе это ровно "анкета ещё
                                     не рассмотрена админом" — см. старый
                                     комментарий в constants.py)

Новый статус "нерезидент" (анкета одобрена, подписки нет) миграцией не
проставляется никому — таких данных в старой системе не было, это только
через ручное решение админа в таблице для конкретных людей.

Запуск: .venv\\Scripts\\python.exe scripts\\migrate_users_statuses_v3.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from constants import SHEET_USERS, USERS_HEADERS
from sheets_client import get_worksheet

_OLD_TO_NEW = {
    "активный": "резидент",
    "неактивный": "на рассмотрении",
}


def main():
    ws = get_worksheet(SHEET_USERS)
    values = ws.get_all_values()
    if not values:
        print("Лист пуст, нечего мигрировать.")
        return

    headers = values[0]
    if "Статус" not in headers:
        print("Колонки «Статус» нет в листе, миграция не применима.")
        return
    status_col = headers.index("Статус")

    updates = []
    unrecognized = []
    for row_number, row in enumerate(values[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue
        old_status = (row[status_col] if status_col < len(row) else "").strip()
        if not old_status:
            continue
        new_status = _OLD_TO_NEW.get(old_status)
        if new_status is None:
            unrecognized.append((row_number, old_status))
            continue
        if new_status != old_status:
            updates.append((row_number, new_status))

    for row_number, new_status in updates:
        ws.update_cell(row_number, status_col + 1, new_status)
        print(f"  строка {row_number}: -> {new_status}")

    print(f"Обновлено строк: {len(updates)}")
    if unrecognized:
        print("Не распознанные значения «Статус» (не тронуты, разберитесь вручную):")
        for row_number, value in unrecognized:
            print(f"  строка {row_number}: {value!r}")


if __name__ == "__main__":
    main()
