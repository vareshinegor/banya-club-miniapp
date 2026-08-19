"""Пересобирает лист «Пользователи» под новую схему анкеты (8 шагов + статус членства).

Полностью очищает лист (старые тестовые строки использовали другую структуру
колонок и не совместимы с новой) и проставляет актуальные заголовки.

Запуск: .venv\\Scripts\\python.exe scripts\\migrate_users_sheet.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from constants import SHEET_USERS, USERS_HEADERS
from sheets_client import get_worksheet


def main():
    ws = get_worksheet(SHEET_USERS)
    ws.clear()
    ws.update(range_name="A1", values=[USERS_HEADERS])
    print(f"Лист «{SHEET_USERS}» очищен, новые заголовки: {USERS_HEADERS}")


if __name__ == "__main__":
    main()
