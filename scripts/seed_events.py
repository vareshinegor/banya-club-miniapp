"""Добавляет тестовые события в лист «Афиша» для ручного тестирования.

Запуск: .venv\\Scripts\\python.exe scripts\\seed_events.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from constants import SHEET_EVENTS
from sheets_client import get_worksheet

EVENTS = [
    ["Networking-встреча участников клуба", "Закрытая встреча для нетворкинга и обмена контактами", "2026-08-20", "19:00", "Москва, Loft Hall", "1500 ₽", ""],
    ["Мастер-класс по продажам", "Практический разбор кейсов из бизнеса участников", "2026-09-05", "12:00", "Онлайн (Zoom)", "Бесплатно", ""],
    ["Стратегическая сессия: цели на квартал", "Групповая проработка целей с бизнес-коучем", "2026-07-10", "10:00", "Санкт-Петербург, коворкинг «Точка»", "2000 ₽", ""],
]


def main():
    ws = get_worksheet(SHEET_EVENTS)
    for row in EVENTS:
        ws.append_row(row, value_input_option="USER_ENTERED")
        print(f"[+] Добавлено: {row[0]} ({row[2]})")
    print("\nГотово.")


if __name__ == "__main__":
    main()
