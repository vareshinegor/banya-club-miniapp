"""Подготавливает таблицу под листики, рефералку и промокоды:

  * создаёт листы «Листики» (журнал операций), «Рефералы» и «Промокоды»
    (если их ещё нет);
  * дописывает в заголовок листа «Записи» колонки «Листики», «Промокод»,
    «К оплате» (существующие строки не трогает — там останутся пустые ячейки);
  * кладёт в «Промокоды» один ВЫКЛЮЧЕННЫЙ пример строки, чтобы был виден формат.

Запуск: .venv\\Scripts\\python.exe scripts\\migrate_wallet_v1.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from constants import (
    POINTS_HEADERS,
    PROMOCODES_HEADERS,
    REFERRALS_HEADERS,
    SHEET_POINTS,
    SHEET_PROMOCODES,
    SHEET_REFERRALS,
    SHEET_SIGNUPS,
    SIGNUPS_HEADERS,
)
from sheets_client import get_spreadsheet


def ensure_sheet(spreadsheet, existing, title, headers):
    if title in existing:
        ws = existing[title]
        if not ws.row_values(1):
            ws.update(range_name="A1", values=[headers])
            print(f"[=] Лист «{title}» был пуст — заголовки добавлены")
        else:
            print(f"[=] Лист «{title}» уже есть, не трогаю")
        return ws
    ws = spreadsheet.add_worksheet(title=title, rows=1000, cols=len(headers))
    ws.update(range_name="A1", values=[headers])
    print(f"[+] Создан лист «{title}»: {headers}")
    return ws


def extend_signups_headers(spreadsheet, existing):
    ws = existing[SHEET_SIGNUPS]
    current = ws.row_values(1)
    if current == SIGNUPS_HEADERS:
        print(f"[=] В листе «{SHEET_SIGNUPS}» колонки уже на месте")
        return
    if current != SIGNUPS_HEADERS[: len(current)]:
        raise SystemExit(
            f"Заголовок листа «{SHEET_SIGNUPS}» {current} не совпадает с ожидаемым началом "
            f"{SIGNUPS_HEADERS[: len(current)]} — останавливаюсь, чтобы ничего не испортить."
        )
    new_cols = SIGNUPS_HEADERS[len(current):]
    # Записываем ячейки заголовка и убеждаемся, что в листе хватает колонок.
    if ws.col_count < len(SIGNUPS_HEADERS):
        ws.add_cols(len(SIGNUPS_HEADERS) - ws.col_count)
    for offset, title in enumerate(new_cols):
        ws.update_cell(1, len(current) + offset + 1, title)
    print(f"[+] В лист «{SHEET_SIGNUPS}» добавлены колонки: {new_cols}")


def main():
    spreadsheet = get_spreadsheet()
    existing = {ws.title: ws for ws in spreadsheet.worksheets()}

    ensure_sheet(spreadsheet, existing, SHEET_POINTS, POINTS_HEADERS)
    ensure_sheet(spreadsheet, existing, SHEET_REFERRALS, REFERRALS_HEADERS)
    promo_ws = ensure_sheet(spreadsheet, existing, SHEET_PROMOCODES, PROMOCODES_HEADERS)
    extend_signups_headers(spreadsheet, existing)

    if len(promo_ws.get_all_values()) <= 1:
        promo_ws.append_row(
            ["ПРИМЕР", "процент", 100, "все", "", "", "нет"],
            value_input_option="RAW",
        )
        print("[+] В «Промокоды» добавлена выключенная строка-пример (Активен = нет)")


if __name__ == "__main__":
    main()
