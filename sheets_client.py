import json
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from config import Config
from constants import (
    POINTS_REASON_ORDER,
    POINTS_REASON_REFERRAL,
    POINTS_REASON_REFUND,
    POINTS_RESERVATION_TTL_MINUTES,
    REFERRAL_REWARD_POINTS,
    SHEET_ACHIEVEMENTS,
    SHEET_EVENTS,
    SHEET_GENERAL,
    SHEET_MATERIALS,
    SHEET_POINTS,
    SHEET_PROMOCODES,
    SHEET_REFERRALS,
    SHEET_SIGNUPS,
    SHEET_USERS,
    SIGNUP_STATUS_FAILED,
    SIGNUP_STATUS_PAID,
    SIGNUP_STATUS_PENDING,
    SIGNUPS_HEADERS,
    STATUS_NON_RESIDENT,
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


def _get_all_values(ws):
    """ws.get_all_values() с повтором при 429 (лимит Google Sheets — 60 чтений в
    минуту на сервисный аккаунт): короткий всплеск запросов не должен ронять
    ответ пользователю ошибкой 500."""
    for attempt in range(3):
        try:
            return ws.get_all_values()
        except gspread.exceptions.APIError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status != 429 or attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))


# Для fresh=True: данные не старше этого срока считаем свежими. Полностью
# обходить кэш нельзя — один заказ читает те же листы по 5-6 раз подряд и
# упирался бы в лимит Google на чтения; 2 секунды при этом на порядок короче
# обычных 8, так что запись из соседнего процесса видна почти сразу.
_FRESH_TTL = 2.0


def _rows_with_index(ws, fresh=False):
    """Return (headers, [(row_number, record_dict), ...]) skipping the header row.
    fresh=True — кэш не старше _FRESH_TTL вместо обычных 8 секунд: нужно там,
    где решение зависит от денег (баланс листиков, резервы, лимиты
    промокодов) — у каждого воркера gunicorn свой кэш, и запись из соседнего
    процесса иначе была бы не видна до 8 секунд. Собственные записи сбрасывают
    кэш листа сразу (_invalidate_sheet_cache)."""
    cached = _sheet_cache.get(ws.title)
    now = time.monotonic()
    ttl = _FRESH_TTL if fresh else _SHEET_CACHE_TTL
    if cached and now - cached[0] < ttl:
        values = cached[1]
    else:
        values = _get_all_values(ws)
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


def _to_int(value, default=0) -> int:
    try:
        return int(float(re.sub(r"\s", "", str(value)).replace(",", ".")))
    except (TypeError, ValueError):
        return default


def _is_stale(date_str: str) -> bool:
    """Заказ старше POINTS_RESERVATION_TTL_MINUTES? Непонятная дата — не считаем
    просроченной (лучше подержать резерв, чем вернуть листики по ошибке)."""
    try:
        created = datetime.strptime((date_str or "").strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        return False
    return datetime.now() - created > timedelta(minutes=POINTS_RESERVATION_TTL_MINUTES)


# --- Пользователи -----------------------------------------------------


def find_user(telegram_id) -> Optional[dict]:
    ws = get_worksheet(SHEET_USERS)
    _, rows = _rows_with_index(ws)
    for row_number, record in rows:
        if str(record.get("telegram_id", "")) == str(telegram_id):
            record["_row"] = row_number
            return record
    return None


def create_user(telegram_id, username, sb_id, fields: dict, avatar_url: str = ""):
    """fields: {header_name: value} for any subset of USERS_HEADERS. telegram_id,
    username, sb_id, Статус и Дата регистрации проставляются здесь автоматически.
    avatar_url — если фото уже загружено на шаге анкеты (он идёт раньше, чем
    вызывается create_user)."""
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
        elif header == "Аватарка":
            row.append(avatar_url or "")
        else:
            row.append(fields.get(header, ""))
    ws.append_row(row, value_input_option="RAW")
    _invalidate_sheet_cache(SHEET_USERS)


def set_avatar_url(telegram_id, url: str) -> bool:
    """Записывает ссылку на аватар в колонку "Аватарка". Не ошибка, если строки
    ещё нет (загрузка фото на шаге анкеты происходит раньше, чем создаётся
    строка пользователя) — тогда просто ничего не делает, create_user() сам
    проставит ссылку при регистрации."""
    ws = get_worksheet(SHEET_USERS)
    headers, rows = _rows_with_index(ws)
    if "Аватарка" not in headers:
        return False
    col = headers.index("Аватарка") + 1
    for row_number, record in rows:
        if str(record.get("telegram_id", "")) == str(telegram_id):
            ws.update_cell(row_number, col, url)
            _invalidate_sheet_cache(SHEET_USERS)
            return True
    return False


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


def mark_reviewed_non_resident(telegram_id, sb_id: str = "") -> bool:
    """Анкета рассмотрена и одобрена вебхуком salebot, но подписку человек ещё
    не купил — переводит в STATUS_NON_RESIDENT. Не трогает уже оплативших
    (STATUS_RESIDENT), чтобы повторный/запоздавший вызов не понижал резидента
    обратно. sb_id — как в mark_subscription_paid, дозаписывается только если
    поле пустое. Возвращает False, если такого telegram_id нет в таблице."""
    ws = get_worksheet(SHEET_USERS)
    headers, rows = _rows_with_index(ws)
    col_map = {h: i + 1 for i, h in enumerate(headers)}
    for row_number, record in rows:
        if str(record.get("telegram_id", "")) == str(telegram_id):
            current = (record.get("Статус") or "").strip().casefold()
            if current != STATUS_RESIDENT.casefold():
                ws.update_cell(row_number, col_map["Статус"], STATUS_NON_RESIDENT)
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


def create_pending_signup(
    telegram_id,
    event_id,
    order_id: str,
    quantity: int = 1,
    points: int = 0,
    promo: str = "",
    due: int = 0,
    status: str = SIGNUP_STATUS_PENDING,
):
    """Создаёт (или переиспользует существующую неоплаченную) строку записи
    со статусом "ожидает оплаты" перед тем, как отправить пользователя на
    оплату — чтобы повторные попытки не плодили дубли строк. Количество,
    листики, промокод и сумма перезаписываются и при переиспользовании —
    пользователь мог поменять условия между попытками оплаты. status=PAID
    используется для заказов, закрытых целиком листиками/промокодом (в
    Продамус они не уходят)."""
    ws = get_worksheet(SHEET_SIGNUPS)
    _, rows = _rows_with_index(ws, fresh=True)
    values = [
        str(telegram_id), str(event_id), _now(), status, order_id, int(quantity),
        int(points), promo or "", int(due),
    ]
    last_col = chr(ord("A") + len(SIGNUPS_HEADERS) - 1)
    for row_number, record in rows:
        if (
            str(record.get("telegram_id", "")) == str(telegram_id)
            and str(record.get("ID события", "")) == str(event_id)
            and record.get("Статус") != SIGNUP_STATUS_PAID
        ):
            ws.update(
                range_name=f"A{row_number}:{last_col}{row_number}",
                values=[values],
                value_input_option="RAW",
            )
            _invalidate_sheet_cache(SHEET_SIGNUPS)
            return

    ws.append_row(values, value_input_option="RAW")
    _invalidate_sheet_cache(SHEET_SIGNUPS)


def find_signup_by_order(order_id: str, fresh: bool = False) -> Optional[dict]:
    ws = get_worksheet(SHEET_SIGNUPS)
    _, rows = _rows_with_index(ws, fresh=fresh)
    for row_number, record in rows:
        if record.get("Заказ") == order_id:
            record["_row"] = row_number
            return record
    return None


def settle_signup(order_id: str, status: str) -> bool:
    """Проставляет итоговый статус записи по order_id (вебхук Продамуса или
    откат неудавшегося заказа) и приводит резерв листиков в соответствие:
    оплачено — листики списаны, отклонено — возвращены. Безопасно вызывать
    повторно (Продамус может прислать вебхук дважды) — см.
    set_order_points_net. Возвращает False, если такого заказа нет."""
    record = find_signup_by_order(order_id, fresh=True)
    if not record:
        return False
    ws = get_worksheet(SHEET_SIGNUPS)
    ws.update_cell(record["_row"], SIGNUPS_HEADERS.index("Статус") + 1, status)
    _invalidate_sheet_cache(SHEET_SIGNUPS)

    points = _to_int(record.get("Листики"))
    if points:
        telegram_id = record.get("telegram_id")
        if status == SIGNUP_STATUS_PAID:
            set_order_points_net(telegram_id, order_id, -points)
        elif status == SIGNUP_STATUS_FAILED:
            set_order_points_net(telegram_id, order_id, 0)
    return True


def release_event_reservation(telegram_id, event_id):
    """Возвращает на баланс листики, зарезервированные под прошлую неоплаченную
    попытку купить именно это событие — новая попытка перезапишет ту же строку,
    и без этого шага резерв прошлой попытки уменьшал бы доступный баланс."""
    ws = get_worksheet(SHEET_SIGNUPS)
    _, rows = _rows_with_index(ws, fresh=True)
    for _, record in rows:
        if (
            str(record.get("telegram_id", "")) == str(telegram_id)
            and str(record.get("ID события", "")) == str(event_id)
            and record.get("Статус") != SIGNUP_STATUS_PAID
        ):
            order_id = record.get("Заказ")
            if order_id and _to_int(record.get("Листики")):
                set_order_points_net(telegram_id, order_id, 0)


def release_stale_reservations(telegram_id):
    """Возвращает листики из неоплаченных заказов старше
    POINTS_RESERVATION_TTL_MINUTES (человек закрыл страницу Продамуса). Сама
    запись остаётся "ожидает оплаты": если оплата всё-таки придёт позже,
    settle_signup снова спишет листики."""
    ws = get_worksheet(SHEET_SIGNUPS)
    _, rows = _rows_with_index(ws)  # уборка не критична по времени — обычный кэш
    for _, record in rows:
        if (
            str(record.get("telegram_id", "")) == str(telegram_id)
            and record.get("Статус") == SIGNUP_STATUS_PENDING
            and _to_int(record.get("Листики"))
            and _is_stale(record.get("Дата записи"))
        ):
            set_order_points_net(telegram_id, record.get("Заказ"), 0)


# --- Листики (журнал операций) --------------------------------------------


def _points_rows(telegram_id, fresh=False) -> list:
    ws = get_worksheet(SHEET_POINTS)
    _, rows = _rows_with_index(ws, fresh=fresh)
    return [record for _, record in rows if str(record.get("telegram_id", "")) == str(telegram_id)]


def get_points_balance(telegram_id, fresh: bool = False) -> int:
    return sum(_to_int(r.get("Сумма")) for r in _points_rows(telegram_id, fresh=fresh))


def list_points_history(telegram_id, limit: int = 10) -> list:
    rows = _points_rows(telegram_id)
    return [
        {"amount": _to_int(r.get("Сумма")), "reason": r.get("Причина", ""), "date": r.get("Дата", "")}
        for r in reversed(rows)
    ][:limit]


def add_points(telegram_id, amount: int, reason: str, ref: str = ""):
    ws = get_worksheet(SHEET_POINTS)
    ws.append_row([str(telegram_id), int(amount), reason, str(ref), _now()], value_input_option="RAW")
    _invalidate_sheet_cache(SHEET_POINTS)


def order_points_net(telegram_id, order_id) -> int:
    return sum(
        _to_int(r.get("Сумма"))
        for r in _points_rows(telegram_id, fresh=True)
        if str(r.get("Ссылка", "")) == str(order_id)
    )


def set_order_points_net(telegram_id, order_id, target_net: int):
    """Доводит сумму всех операций по заказу до target_net (0 — всё возвращено,
    -N — N листиков списано). Дописывает только недостающую разницу, поэтому
    повторный вызов (дубль вебхука, гонка) ничего не задваивает."""
    delta = int(target_net) - order_points_net(telegram_id, order_id)
    if delta:
        add_points(telegram_id, delta, POINTS_REASON_ORDER if delta < 0 else POINTS_REASON_REFUND, order_id)


# --- Рефералка --------------------------------------------------------------


def record_referral(invited_id, referrer_id) -> bool:
    """Фиксирует, кто привёл человека, при его первом открытии мини-аппа по
    реферальной ссылке (first-touch: повторно не перезаписывается). Игнорирует
    самоприглашение, несуществующего пригласившего и уже зарегистрированных."""
    if str(invited_id) == str(referrer_id):
        return False
    if not find_user(referrer_id) or find_user(invited_id):
        return False
    ws = get_worksheet(SHEET_REFERRALS)
    _, rows = _rows_with_index(ws, fresh=True)
    if any(str(r.get("telegram_id", "")) == str(invited_id) for _, r in rows):
        return False
    ws.append_row([str(invited_id), str(referrer_id), _now(), ""], value_input_option="RAW")
    _invalidate_sheet_cache(SHEET_REFERRALS)
    return True


def grant_referral_reward(invited_id) -> bool:
    """Начисляет пригласившему REFERRAL_REWARD_POINTS, когда анкету приглашённого
    одобрили. Один раз на приглашённого: отметка "Награда" в листе "Рефералы"
    плюс проверка по журналу листиков (на случай, если отметка не успела
    записаться). Возвращает True, если награда начислена сейчас."""
    ws = get_worksheet(SHEET_REFERRALS)
    headers, rows = _rows_with_index(ws, fresh=True)
    for row_number, record in rows:
        if str(record.get("telegram_id", "")) != str(invited_id):
            continue
        if (record.get("Награда") or "").strip():
            return False
        referrer_id = str(record.get("Пригласил", "")).strip()
        if not referrer_id or not find_user(referrer_id):
            return False
        ref = f"ref:{invited_id}"
        already = any(
            str(r.get("Ссылка", "")) == ref and r.get("Причина") == POINTS_REASON_REFERRAL
            for r in _points_rows(referrer_id, fresh=True)
        )
        if not already:
            add_points(referrer_id, REFERRAL_REWARD_POINTS, POINTS_REASON_REFERRAL, ref)
        ws.update_cell(row_number, headers.index("Награда") + 1, _now())
        _invalidate_sheet_cache(SHEET_REFERRALS)
        return not already
    return False


def settle_referral_rewards(referrer_id) -> int:
    """Награды за приглашённых, которых одобрили не вебхуком, а вручную (админ
    поменял "Статус" прямо в таблице) — вебхук в таком случае не приходит, и
    без этой проверки листики бы не начислились никогда. Вызывается, когда
    пригласивший открывает свой кошелёк. Возвращает, сколько наград начислено."""
    ws = get_worksheet(SHEET_REFERRALS)
    _, rows = _rows_with_index(ws)
    approved = {STATUS_NON_RESIDENT.casefold(), STATUS_RESIDENT.casefold()}
    granted = 0
    for _, record in rows:
        if str(record.get("Пригласил", "")) != str(referrer_id) or (record.get("Награда") or "").strip():
            continue
        invited = find_user(record.get("telegram_id"))
        if invited and (invited.get("Статус") or "").strip().casefold() in approved:
            if grant_referral_reward(record.get("telegram_id")):
                granted += 1
    return granted


def referral_stats(referrer_id) -> dict:
    ws = get_worksheet(SHEET_REFERRALS)
    _, rows = _rows_with_index(ws)
    mine = [r for _, r in rows if str(r.get("Пригласил", "")) == str(referrer_id)]
    return {"total": len(mine), "rewarded": sum(1 for r in mine if (r.get("Награда") or "").strip())}


# --- Промокоды --------------------------------------------------------------


def find_promo(code: str, fresh: bool = False) -> Optional[dict]:
    target = (code or "").strip().casefold()
    if not target:
        return None
    ws = get_worksheet(SHEET_PROMOCODES)
    _, rows = _rows_with_index(ws, fresh=fresh)
    for _, record in rows:
        if (record.get("Код") or "").strip().casefold() == target:
            return record
    return None


def promo_uses(code: str, exclude_telegram_id=None, exclude_event_id=None) -> int:
    """Сколько раз код уже применён: оплаченные записи + неоплаченные, но ещё не
    просроченные (см. POINTS_RESERVATION_TTL_MINUTES). Считается по листу
    "Записи", а не счётчиком в промокоде — отклонённые заказы сами перестают
    учитываться. Неоплаченная попытка самого пользователя на это же событие
    не считается — она будет перезаписана новой."""
    target = (code or "").strip().casefold()
    ws = get_worksheet(SHEET_SIGNUPS)
    _, rows = _rows_with_index(ws, fresh=True)
    uses = 0
    for _, record in rows:
        if (record.get("Промокод") or "").strip().casefold() != target:
            continue
        status = record.get("Статус")
        if status == SIGNUP_STATUS_PAID:
            uses += 1
        elif status == SIGNUP_STATUS_PENDING and not _is_stale(record.get("Дата записи")):
            own = (
                exclude_telegram_id is not None
                and str(record.get("telegram_id", "")) == str(exclude_telegram_id)
                and str(record.get("ID события", "")) == str(exclude_event_id)
            )
            if not own:
                uses += 1
    return uses


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
        attendees.append({"telegram_id": telegram_id, "fio": user.get("ФИО", ""), "niche": niche, "quantity": quantity})
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
