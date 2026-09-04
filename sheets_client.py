import json
import threading
import time
from datetime import datetime
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from config import Config
from constants import (
    SHEET_ACHIEVEMENTS,
    SHEET_EVENTS,
    SHEET_GENERAL,
    SHEET_MATERIALS,
    SHEET_SIGNUPS,
    SHEET_USERS,
    SIGNUP_STATUS_PAID,
    SIGNUP_STATUS_PENDING,
    SIGNUPS_HEADERS,
    STATUS_PENDING,
    STATUS_RESIDENT,
    USERS_HEADERS,
)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_client = None
_spreadsheet = None
_worksheets_by_name = {}
# RLock, а не Lock: get_worksheet -> get_spreadsheet -> get_client вложенно
# берут одну и ту же блокировку из одного потока — обычный Lock тут
# самозаблокировался бы намертво.
_init_lock = threading.RLock()

# Каждый round-trip к Google Sheets — от 600мс до нескольких секунд, а один
# заход на Главную дёргает 4-5 таких чтений (в т.ч. один и тот же лист
# "Пользователи" — в /api/auth и потом ещё раз в /api/events). Кэшируем
# содержимое листа на несколько секунд: этого достаточно, чтобы схлопнуть все
# чтения одного запроса/перехода по вкладкам в один реальный вызов к API, но
# админ, поменявший что-то в таблице руками, увидит изменения почти сразу.
_SHEET_CACHE_TTL = 8
_sheet_cache = {}


def _invalidate_sheet_cache(name: str):
    _sheet_cache.pop(name, None)


def get_client():
    global _client
    if _client is None:
        # Flask работает с threaded=True — без блокировки два одновременных
        # первых запроса могли бы параллельно логиниться в Google по второму разу.
        with _init_lock:
            if _client is None:
                if Config.GOOGLE_CREDENTIALS_JSON:
                    info = json.loads(Config.GOOGLE_CREDENTIALS_JSON)
                    creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
                else:
                    creds = Credentials.from_service_account_file(Config.GOOGLE_CREDENTIALS_FILE, scopes=_SCOPES)
                _client = gspread.authorize(creds)
    return _client


def get_spreadsheet():
    global _spreadsheet
    if _spreadsheet is None:
        with _init_lock:
            if _spreadsheet is None:
                _spreadsheet = get_client().open_by_key(Config.GOOGLE_SHEETS_ID)
    return _spreadsheet


def get_worksheet(name: str):
    # worksheet(name) would otherwise re-fetch sheet metadata on every single call
    # (an extra Sheets API round trip each time) — cache the handle per process.
    if name not in _worksheets_by_name:
        with _init_lock:
            if name not in _worksheets_by_name:
                _worksheets_by_name[name] = get_spreadsheet().worksheet(name)
    return _worksheets_by_name[name]


def _rows_with_index(ws):
    """Return (headers, [(row_number, record_dict), ...]) skipping the header row."""
    cached = _sheet_cache.get(ws.title)
    now = time.monotonic()
    if cached and now - cached[0] < _SHEET_CACHE_TTL:
        values = cached[1]
    else:
        values = ws.get_all_values()
        _sheet_cache[ws.title] = (now, values)
    if not values:
        return [], []
    headers = values[0]
    rows = []
    for i, row in enumerate(values[1:], start=2):
        record = {headers[j]: (row[j] if j < len(row) else "") for j in range(len(headers))}
        rows.append((i, record))
    return headers, rows


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# --- Пользователи -----------------------------------------------------


def find_user(telegram_id) -> Optional[dict]:
    ws = get_worksheet(SHEET_USERS)
    _, rows = _rows_with_index(ws)
    for row_number, record in rows:
        if str(record.get("telegram_id", "")) == str(telegram_id):
            record["_row"] = row_number
            return record
    return None


def create_user(telegram_id, username, sb_id, fields: dict):
    """fields: {header_name: value} for any subset of USERS_HEADERS. telegram_id,
    username, sb_id, Статус и Дата регистрации проставляются здесь автоматически."""
    ws = get_worksheet(SHEET_USERS)
    row = []
    for header in USERS_HEADERS:
        if header == "telegram_id":
            row.append(str(telegram_id))
        elif header == "username":
            row.append(username or "")
        elif header == "sb_id":
            row.append(sb_id or "")
        elif header == "Статус":
            row.append(STATUS_PENDING)
        elif header == "Дата регистрации":
            row.append(_now())
        else:
            row.append(fields.get(header, ""))
    ws.append_row(row, value_input_option="RAW")
    _invalidate_sheet_cache(SHEET_USERS)


def mark_subscription_paid(telegram_id, sb_id: str = "") -> bool:
    """Подписка подтверждена вебхуком salebot (оплата проходит у них, не в
    нашем Продамусе) — переводит пользователя в STATUS_RESIDENT. sb_id
    дозаписывается только если в таблице это поле ещё пустое (не затираем
    уже сохранённое значение). Возвращает False, если такого telegram_id нет
    в листе "Пользователи" (например, вебхук пришёл раньше анкеты)."""
    ws = get_worksheet(SHEET_USERS)
    headers, rows = _rows_with_index(ws)
    col_map = {h: i + 1 for i, h in enumerate(headers)}
    for row_number, record in rows:
        if str(record.get("telegram_id", "")) == str(telegram_id):
            ws.update_cell(row_number, col_map["Статус"], STATUS_RESIDENT)
            if sb_id and not (record.get("sb_id") or "").strip():
                ws.update_cell(row_number, col_map["sb_id"], str(sb_id))
            _invalidate_sheet_cache(SHEET_USERS)
            return True
    return False


# --- Общие (данные от сейлбота) --------------------------------------------


def save_platform_id(telegram_id, platform_id):
    """Апсерт связки telegram_id -> platform_id в лист "Общие"."""
    ws = get_worksheet(SHEET_GENERAL)
    headers, rows = _rows_with_index(ws)
    for row_number, record in rows:
        if str(record.get("telegram_id", "")) == str(telegram_id):
            col_map = {h: i + 1 for i, h in enumerate(headers)}
            ws.update_cell(row_number, col_map["platform_id"], str(platform_id))
            ws.update_cell(row_number, col_map["Дата получения"], _now())
            _invalidate_sheet_cache(SHEET_GENERAL)
            return
    ws.append_row([str(telegram_id), str(platform_id), _now()], value_input_option="RAW")
    _invalidate_sheet_cache(SHEET_GENERAL)


def find_platform_id(telegram_id) -> Optional[str]:
    ws = get_worksheet(SHEET_GENERAL)
    _, rows = _rows_with_index(ws)
    for _, record in rows:
        if str(record.get("telegram_id", "")) == str(telegram_id):
            return record.get("platform_id", "")
    return None


# --- Афиша --------------------------------------------------------------


def list_events() -> list:
    """Читает Афишу. У каждого события — свой ID из колонки "ID", а не номер
    строки: строки можно удалять/переставлять, не ломая ссылки на события из
    листа "Записи". Если админ добавил событие вручную и не проставил ID —
    подставляем и дописываем в таблицу сами (следующий свободный номер)."""
    ws = get_worksheet(SHEET_EVENTS)
    _, rows = _rows_with_index(ws)
    active_rows = [(row_number, record) for row_number, record in rows if record.get("Название")]

    max_id = 0
    for _, record in active_rows:
        raw_id = (record.get("ID") or "").strip()
        if raw_id.isdigit():
            max_id = max(max_id, int(raw_id))

    events = []
    backfilled = False
    for row_number, record in active_rows:
        raw_id = (record.get("ID") or "").strip()
        if not raw_id:
            max_id += 1
            raw_id = str(max_id)
            ws.update_cell(row_number, 1, raw_id)
            backfilled = True
        record["id"] = raw_id
        events.append(record)
    if backfilled:
        _invalidate_sheet_cache(SHEET_EVENTS)
    return events


def get_event(event_id) -> Optional[dict]:
    target = str(event_id)
    for event in list_events():
        if str(event["id"]) == target:
            return event
    return None


# --- Записи на мероприятия ----------------------------------------------
#
# Статус записи проходит путь "ожидает оплаты" -> "оплачено"/"отклонено".
# Строка создаётся (или переиспользуется) в момент формирования ссылки на
# оплату Продамуса, ДО того как пользователь реально заплатил — и только
# вебхук с валидной подписью переводит её в "оплачено". Пользователю
# запись/список показываем только когда она реально оплачена.


def list_signups_for_user(telegram_id) -> list:
    """Только оплаченные записи — то, что видит сам пользователь."""
    ws = get_worksheet(SHEET_SIGNUPS)
    _, rows = _rows_with_index(ws)
    return [
        record for _, record in rows
        if str(record.get("telegram_id", "")) == str(telegram_id)
        and record.get("Статус") == SIGNUP_STATUS_PAID
    ]


def is_signed_up(telegram_id, event_id) -> bool:
    signups = list_signups_for_user(telegram_id)
    return any(str(s.get("ID события")) == str(event_id) for s in signups)


def get_signup_quantity(telegram_id, event_id) -> int:
    """Сколько билетов оплачено этим пользователем на это событие (0, если не записан)."""
    for s in list_signups_for_user(telegram_id):
        if str(s.get("ID события")) == str(event_id):
            try:
                return int(s.get("Количество") or 1)
            except ValueError:
                return 1
    return 0


def create_pending_signup(telegram_id, event_id, order_id: str, quantity: int = 1):
    """Создаёт (или переиспользует существующую неоплаченную) строку записи
    со статусом "ожидает оплаты" перед тем, как отправить пользователя на
    оплату — чтобы повторные попытки не плодили дубли строк. quantity
    перезаписывается и при переиспользовании — пользователь мог поменять
    число билетов между попытками оплаты."""
    ws = get_worksheet(SHEET_SIGNUPS)
    _, rows = _rows_with_index(ws)
    for row_number, record in rows:
        if (
            str(record.get("telegram_id", "")) == str(telegram_id)
            and str(record.get("ID события", "")) == str(event_id)
            and record.get("Статус") != SIGNUP_STATUS_PAID
        ):
            col = SIGNUPS_HEADERS.index("Статус") + 1
            order_col = SIGNUPS_HEADERS.index("Заказ") + 1
            date_col = SIGNUPS_HEADERS.index("Дата записи") + 1
            qty_col = SIGNUPS_HEADERS.index("Количество") + 1
            ws.update_cell(row_number, col, SIGNUP_STATUS_PENDING)
            ws.update_cell(row_number, order_col, order_id)
            ws.update_cell(row_number, date_col, _now())
            ws.update_cell(row_number, qty_col, str(quantity))
            _invalidate_sheet_cache(SHEET_SIGNUPS)
            return

    ws.append_row(
        [str(telegram_id), str(event_id), _now(), SIGNUP_STATUS_PENDING, order_id, str(quantity)],
        value_input_option="RAW",
    )
    _invalidate_sheet_cache(SHEET_SIGNUPS)


def find_signup_by_order(order_id: str) -> Optional[dict]:
    ws = get_worksheet(SHEET_SIGNUPS)
    _, rows = _rows_with_index(ws)
    for row_number, record in rows:
        if record.get("Заказ") == order_id:
            record["_row"] = row_number
            return record
    return None


def set_signup_status(order_id: str, status: str) -> bool:
    """Обновляет статус записи по order_id (из вебхука Продамуса).
    Возвращает False, если строка с таким заказом не найдена."""
    record = find_signup_by_order(order_id)
    if not record:
        return False
    ws = get_worksheet(SHEET_SIGNUPS)
    col = SIGNUPS_HEADERS.index("Статус") + 1
    ws.update_cell(record["_row"], col, status)
    _invalidate_sheet_cache(SHEET_SIGNUPS)
    return True


def list_attendees(event_id) -> list:
    """ФИО всех, кто оплатил событие (по данным листов Записи + Пользователи).
    quantity — сколько билетов купил именно этот человек (для подсчёта общего
    числа мест на событие, а не только числа зарегистрировавшихся)."""
    signups_ws = get_worksheet(SHEET_SIGNUPS)
    _, signup_rows = _rows_with_index(signups_ws)
    attendee_entries = [
        (str(record.get("telegram_id", "")), record.get("Количество"))
        for _, record in signup_rows
        if str(record.get("ID события", "")) == str(event_id)
        and record.get("Статус") == SIGNUP_STATUS_PAID
    ]
    if not attendee_entries:
        return []

    users_ws = get_worksheet(SHEET_USERS)
    _, user_rows = _rows_with_index(users_ws)
    users_by_id = {str(record.get("telegram_id", "")): record for _, record in user_rows}

    attendees = []
    for telegram_id, raw_quantity in attendee_entries:
        user = users_by_id.get(telegram_id)
        if not user:
            continue
        try:
            quantity = int(raw_quantity or 1)
        except ValueError:
            quantity = 1
        first_sphere = (user.get("Сфера", "") or "").split(",")[0].strip()
        niche = " · ".join(part for part in (first_sphere, user.get("Компания/Проект", "")) if part)
        attendees.append({"fio": user.get("ФИО", ""), "niche": niche, "quantity": quantity})
    return attendees


# --- Материалы ------------------------------------------------------------


def list_materials() -> list:
    ws = get_worksheet(SHEET_MATERIALS)
    _, rows = _rows_with_index(ws)
    materials = []
    for row_number, record in rows:
        if not record.get("Название"):
            continue
        record["id"] = row_number
        materials.append(record)
    return materials


# --- Достижения -----------------------------------------------------------


def list_achievements_for_user(telegram_id) -> list:
    ws = get_worksheet(SHEET_ACHIEVEMENTS)
    _, rows = _rows_with_index(ws)
    return [record for _, record in rows if str(record.get("telegram_id", "")) == str(telegram_id)]
