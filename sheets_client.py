from datetime import datetime
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from config import Config
from constants import (
    SHEET_ACHIEVEMENTS,
    SHEET_EVENTS,
    SHEET_MATERIALS,
    SHEET_SIGNUPS,
    SHEET_USERS,
    SIGNUP_STATUS_PAID,
    STATUS_INACTIVE,
)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_client = None
_spreadsheet = None
_worksheets_by_name = {}


def get_client():
    global _client
    if _client is None:
        creds = Credentials.from_service_account_file(Config.GOOGLE_CREDENTIALS_FILE, scopes=_SCOPES)
        _client = gspread.authorize(creds)
    return _client


def get_spreadsheet():
    global _spreadsheet
    if _spreadsheet is None:
        _spreadsheet = get_client().open_by_key(Config.GOOGLE_SHEETS_ID)
    return _spreadsheet


def get_worksheet(name: str):
    # worksheet(name) would otherwise re-fetch sheet metadata on every single call
    # (an extra Sheets API round trip each time) — cache the handle per process.
    if name not in _worksheets_by_name:
        _worksheets_by_name[name] = get_spreadsheet().worksheet(name)
    return _worksheets_by_name[name]


def _rows_with_index(ws):
    """Return (headers, [(row_number, record_dict), ...]) skipping the header row."""
    values = ws.get_all_values()
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


def create_user(telegram_id, username, fio, dob, company, sphere, role, request_text, offer, source):
    ws = get_worksheet(SHEET_USERS)
    ws.append_row(
        [
            str(telegram_id),
            username or "",
            fio,
            dob,
            company,
            sphere,
            role,
            request_text,
            offer,
            source,
            STATUS_INACTIVE,
            _now(),
        ],
        value_input_option="RAW",
    )


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
    for row_number, record in active_rows:
        raw_id = (record.get("ID") or "").strip()
        if not raw_id:
            max_id += 1
            raw_id = str(max_id)
            ws.update_cell(row_number, 1, raw_id)
        record["id"] = raw_id
        events.append(record)
    return events


def get_event(event_id) -> Optional[dict]:
    target = str(event_id)
    for event in list_events():
        if str(event["id"]) == target:
            return event
    return None


# --- Записи на мероприятия ----------------------------------------------


def list_signups_for_user(telegram_id) -> list:
    ws = get_worksheet(SHEET_SIGNUPS)
    _, rows = _rows_with_index(ws)
    return [record for _, record in rows if str(record.get("telegram_id", "")) == str(telegram_id)]


def is_signed_up(telegram_id, event_id) -> bool:
    signups = list_signups_for_user(telegram_id)
    return any(str(s.get("ID события")) == str(event_id) for s in signups)


def add_signup(telegram_id, event_id):
    ws = get_worksheet(SHEET_SIGNUPS)
    ws.append_row(
        [str(telegram_id), str(event_id), _now(), SIGNUP_STATUS_PAID],
        value_input_option="RAW",
    )


def list_attendees(event_id) -> list:
    """ФИО всех, кто записан на событие (по данным листов Записи + Пользователи)."""
    signups_ws = get_worksheet(SHEET_SIGNUPS)
    _, signup_rows = _rows_with_index(signups_ws)
    attendee_ids = [
        str(record.get("telegram_id", ""))
        for _, record in signup_rows
        if str(record.get("ID события", "")) == str(event_id)
    ]
    if not attendee_ids:
        return []

    users_ws = get_worksheet(SHEET_USERS)
    _, user_rows = _rows_with_index(users_ws)
    users_by_id = {str(record.get("telegram_id", "")): record for _, record in user_rows}

    attendees = []
    for telegram_id in attendee_ids:
        user = users_by_id.get(telegram_id)
        if user:
            attendees.append({"fio": user.get("ФИО", "")})
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
