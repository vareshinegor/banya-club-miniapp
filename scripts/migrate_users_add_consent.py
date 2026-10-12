"""Добавляет колонку «Согласие ПДн» в конец листа «Пользователи» — туда пишется
время, когда человек поставил галочку согласия на обработку персональных
данных при подаче заявки. Ничего не стирает и не переписывает: только
дописывает заголовок в первую строку (у уже зарегистрированных ячейка пустая —
у них согласие в приложении не запрашивалось).

Запуск: .venv\\Scripts\\python.exe scripts\\migrate_users_add_consent.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from constants import SHEET_USERS
from sheets_client import get_worksheet

HEADER = "Согласие ПДн"


def main():
    ws = get_worksheet(SHEET_USERS)
    headers = ws.row_values(1)
    if HEADER in headers:
        print(f"Колонка «{HEADER}» уже есть (№{headers.index(HEADER) + 1}), миграция не нужна.")
        return
    col = len(headers) + 1
    if col > ws.col_count:
        ws.add_cols(col - ws.col_count)  # в сетке листа нет свободной колонки
    ws.update_cell(1, col, HEADER)
    print(f"Добавлена колонка «{HEADER}» (№{col}) в лист «{SHEET_USERS}».")


if __name__ == "__main__":
    main()
