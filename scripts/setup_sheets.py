"""
Одноразовый скрипт: создаёт недостающие листы в Google Таблице
(Пользователи/Афиша/Записи/Материалы/Достижения) и проставляет
заголовки первой строкой, если лист пустой.

Запуск: .venv\\Scripts\\python.exe scripts\\setup_sheets.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from constants import (
    ACHIEVEMENTS_HEADERS,
    EVENTS_HEADERS,
    MATERIALS_HEADERS,
    SHEET_ACHIEVEMENTS,
    SHEET_EVENTS,
    SHEET_MATERIALS,
    SHEET_SIGNUPS,
    SHEET_USERS,
    SIGNUPS_HEADERS,
    USERS_HEADERS,
)
from sheets_client import get_spreadsheet

SHEETS = [
    (SHEET_USERS, USERS_HEADERS),
    (SHEET_EVENTS, EVENTS_HEADERS),
    (SHEET_SIGNUPS, SIGNUPS_HEADERS),
    (SHEET_MATERIALS, MATERIALS_HEADERS),
    (SHEET_ACHIEVEMENTS, ACHIEVEMENTS_HEADERS),
]


def main():
    spreadsheet = get_spreadsheet()
    existing = {ws.title: ws for ws in spreadsheet.worksheets()}

    for name, headers in SHEETS:
        if name in existing:
            ws = existing[name]
            first_row = ws.row_values(1)
            if not first_row:
                ws.update(range_name="A1", values=[headers])
                print(f"[=] Лист «{name}» уже существовал, но был пуст — заголовки добавлены")
            else:
                print(f"[=] Лист «{name}» уже существует, заголовки не трогаю")
        else:
            ws = spreadsheet.add_worksheet(title=name, rows=200, cols=len(headers))
            ws.update(range_name="A1", values=[headers])
            print(f"[+] Создан лист «{name}» с заголовками")

    # Google Sheets создаёт таблицу с одним листом "Sheet1"/"Лист1" по умолчанию.
    # Если он остался пустым и не входит в наш список — удаляем, чтобы не путал.
    default_names = {"Sheet1", "Лист1"}
    our_names = {name for name, _ in SHEETS}
    for ws in spreadsheet.worksheets():
        if ws.title in default_names and ws.title not in our_names:
            if not ws.get_all_values():
                spreadsheet.del_worksheet(ws)
                print(f"[-] Удалён пустой лист по умолчанию «{ws.title}»")

    print("\nГотово. Листы в таблице:", [ws.title for ws in spreadsheet.worksheets()])


if __name__ == "__main__":
    main()
