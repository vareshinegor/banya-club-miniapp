"""Создаёт лист «Общие» (связка telegram_id -> platform_id от сейлбота),
если его ещё нет.

Запуск: .venv\\Scripts\\python.exe scripts\\setup_general_sheet.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from constants import GENERAL_HEADERS, SHEET_GENERAL
from sheets_client import get_spreadsheet


def main():
    spreadsheet = get_spreadsheet()
    existing = {ws.title: ws for ws in spreadsheet.worksheets()}

    if SHEET_GENERAL in existing:
        ws = existing[SHEET_GENERAL]
        if not ws.row_values(1):
            ws.update(range_name="A1", values=[GENERAL_HEADERS])
            print(f"[=] Лист «{SHEET_GENERAL}» уже существовал, но был пуст — заголовки добавлены")
        else:
            print(f"[=] Лист «{SHEET_GENERAL}» уже существует, заголовки не трогаю")
        return

    ws = spreadsheet.add_worksheet(title=SHEET_GENERAL, rows=500, cols=len(GENERAL_HEADERS))
    ws.update(range_name="A1", values=[GENERAL_HEADERS])
    print(f"[+] Создан лист «{SHEET_GENERAL}» с заголовками {GENERAL_HEADERS}")


if __name__ == "__main__":
    main()
