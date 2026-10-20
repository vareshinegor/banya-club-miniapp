"""Админ-панель Банного Ордена — отдельный сайт на /admin (в браузере, не в
Telegram): люди (резиденты / нерезиденты / заявки), афиша, записи на события,
дубики, промокоды, материалы, журнал действий.

Безопасность (панель показывает персональные данные и меняет деньги/статусы):
  * вход по логину и паролю из переменных окружения (ADMIN_LOGIN / ADMIN_PASSWORD).
    Без ADMIN_PASSWORD панель выключена. Пароль сравниваем в постоянное время;
    после 5 неудачных попыток с одного IP вход блокируется на 15 минут;
  * сессия — отдельная подписанная кука banya_admin (HttpOnly, Secure,
    SameSite=Strict, только на /admin, живёт 12 часов), не связанная с сессией
    мини-аппа;
  * все изменяющие запросы требуют заголовок X-CSRF-Token (токен лежит в самой
    куке и отдаётся странице через /admin/api/me) и совпадающий Origin;
  * ответы не кэшируются, страница запрещена к показу во фреймах, CSP без
    inline-скриптов; клиентский код строит DOM через textContent — анкеты
    заполняют посторонние люди, им нельзя доверять;
  * каждое изменение пишется в лист «Журнал»;
  * загруженные картинки перекодируются (image_tools), CSV-выгрузки защищены от
    формул Excel.
"""
import csv
import hmac
import io
import re
import secrets
import threading
import time
from datetime import date, datetime
from functools import wraps
from urllib.parse import urlparse

from flask import Blueprint, Response, g, jsonify, make_response, redirect, render_template, request, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.exceptions import RequestEntityTooLarge

import avatar_client
import checkin_tokens
import image_tools
import sheets_client as sheets
from config import Config
from constants import (
    MAX_TICKETS_PER_SIGNUP,
    PROMO_TYPE_PERCENT,
    PROMO_TYPE_RUB,
    SIGNUP_STATUS_FAILED,
    SIGNUP_STATUS_PAID,
    SIGNUP_STATUS_PENDING,
    STATUS_NON_RESIDENT,
    STATUS_PENDING,
    STATUS_RESIDENT,
    USERS_HEADERS,
)
from routes import (
    _absolute_avatar_url,
    _avatar_url,
    _is_free_price,
    _membership_tier,
    _parse_date,
    _reward_referrer,
)

admin = Blueprint("admin", __name__, url_prefix="/admin")

COOKIE = "banya_admin"
SESSION_TTL = 12 * 60 * 60
LOGIN_WINDOW = 15 * 60
LOGIN_MAX_FAILS = 5

_fails = {}  # ip -> [время неудачной попытки, ...]
_fails_lock = threading.Lock()

STATUSES = (STATUS_PENDING, STATUS_NON_RESIDENT, STATUS_RESIDENT)

# Колонки анкеты, которые админ может править (telegram_id, username, sb_id,
# Статус, Дата регистрации, Аватарка, Согласие ПДн — служебные, руками не меняем).
USER_EDITABLE = (
    "ФИО", "Дата рождения", "Компания/Проект", "Должность", "Город", "Телефон",
    "Сфера", "Роль", "Запрос", "Предложение", "Доход", "Как узнал",
)

_SAFE_PATH = re.compile(r"^(/static/[\w\-./]+|https://[^\s\"'<>]+)$")


# --- Вход и сессия -----------------------------------------------------------


def _enabled() -> bool:
    """Панель включена, только если задан пароль и (вне DEV_MODE) настоящий
    SECRET_KEY: подпись сессии с публичным дефолтным ключом подделывается."""
    if not Config.ADMIN_PASSWORD:
        return False
    return Config.DEV_MODE or Config.SECRET_KEY != "dev-secret-key"


def _signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(Config.SECRET_KEY, salt="banya-admin-session-v1")


def _current():
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    try:
        data = _signer().loads(token, max_age=SESSION_TTL)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict) or "u" not in data or "c" not in data:
        return None
    return data


def _blocked(ip: str) -> bool:
    now = time.time()
    with _fails_lock:
        recent = [t for t in _fails.get(ip, []) if now - t < LOGIN_WINDOW]
        _fails[ip] = recent
        return len(recent) >= LOGIN_MAX_FAILS


def _record_fail(ip: str):
    with _fails_lock:
        _fails.setdefault(ip, []).append(time.time())


def _same(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _err(code: str, message: str, status: int = 400):
    return jsonify({"error": code, "message": message}), status


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not _enabled():
            return _err("disabled", "Админ-панель выключена", 503)
        session = _current()
        if not session:
            return _err("unauthorized", "Нужно войти", 401)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if not _same(request.headers.get("X-CSRF-Token", ""), session["c"]):
                return _err("csrf", "Сессия устарела — обновите страницу", 403)
            origin = request.headers.get("Origin")
            if origin and urlparse(origin).netloc != request.host:
                return _err("csrf", "Запрос с чужого сайта отклонён", 403)
        g.admin = session["u"]
        return fn(*args, **kwargs)

    return wrapper


@admin.after_request
def _security_headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    return response


@admin.errorhandler(RequestEntityTooLarge)
def _too_large(_exc):
    return _err("too_large", "Файл слишком большой (максимум 20 МБ)", 413)


@admin.route("/login", methods=["GET", "POST"])
def login():
    if not _enabled():
        return render_template("admin/login.html", disabled=True, error=None), 503
    if request.method == "GET":
        if _current():
            return redirect(url_for("admin.index"))
        return render_template("admin/login.html", disabled=False, error=None)

    ip = request.remote_addr or "?"
    if _blocked(ip):
        return render_template(
            "admin/login.html", disabled=False, error="Слишком много попыток. Подождите 15 минут."
        ), 429

    login_ok = _same(request.form.get("login", "").strip(), Config.ADMIN_LOGIN)
    password_ok = _same(request.form.get("password", ""), Config.ADMIN_PASSWORD)
    if not (login_ok and password_ok):
        _record_fail(ip)
        time.sleep(0.7)  # замедляем перебор
        return render_template("admin/login.html", disabled=False, error="Неверный логин или пароль"), 401

    with _fails_lock:
        _fails.pop(ip, None)
    token = _signer().dumps({"u": Config.ADMIN_LOGIN, "c": secrets.token_urlsafe(24)})
    response = redirect(url_for("admin.index"))
    response.set_cookie(
        COOKIE, token, max_age=SESSION_TTL, httponly=True,
        secure=not Config.DEV_MODE, samesite="Strict", path="/admin",
    )
    sheets.log_admin_action(Config.ADMIN_LOGIN, "Вход", "", f"ip {ip}")
    return response


@admin.route("/logout", methods=["POST"])
def logout():
    response = redirect(url_for("admin.login"), code=303)
    response.delete_cookie(COOKIE, path="/admin")
    return response


@admin.route("/")
def index():
    if not _enabled() or not _current():
        return redirect(url_for("admin.login"))
    return render_template("admin/app.html")


@admin.route("/api/me")
@admin_required
def me():
    return jsonify({"login": g.admin, "csrf": _current()["c"]})


def _log(action: str, target: str = "", details: str = ""):
    sheets.log_admin_action(g.admin, action, target, details)


# --- Вспомогательное ---------------------------------------------------------


def _str(data: dict, key: str, limit: int) -> str:
    return str(data.get(key) or "").strip()[:limit]


def _int(value, default=0) -> int:
    try:
        return int(float(str(value).replace(" ", "").replace(",", ".")))
    except (TypeError, ValueError):
        return default


def _to_float(value) -> float:
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _iso_date(value) -> str:
    """'2026-10-13' | '13.10.2026' -> '2026-10-13'; пусто, если не дата."""
    parsed = _parse_date(str(value or ""))
    return parsed.strftime("%Y-%m-%d") if parsed else ""


def _norm_price(raw) -> str:
    """'' -> ''; 'бесплатно' -> 'Бесплатно'; '15000' / '15 000 ₽' -> '15000 ₽'.
    Поднимает ValueError на непонятное значение."""
    text = str(raw or "").strip()
    if not text:
        return ""
    if text.casefold() in ("бесплатно", "free"):
        return "Бесплатно"
    digits = re.sub(r"[\s₽рубРУБ.]", "", text).replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d+)?", digits):
        raise ValueError(text)
    return f"{int(float(digits))} ₽"


def _safe_path(value: str) -> bool:
    return not value or bool(_SAFE_PATH.match(value))


def _csv_safe(value) -> str:
    """Ячейка, которая начинается с = + - @ , в Excel/Sheets станет формулой —
    анкеты заполняют посторонние люди, поэтому экранируем."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _csv_response(filename: str, header: list, rows: list) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(header)
    for row in rows:
        writer.writerow([_csv_safe(cell) for cell in row])
    body = "﻿" + buffer.getvalue()  # BOM — чтобы Excel открыл кириллицу
    return Response(
        body, mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _user_brief(u: dict, balances: dict, signup_counts: dict) -> dict:
    tid = str(u.get("telegram_id", ""))
    return {
        "telegram_id": tid,
        "username": u.get("username", ""),
        "fio": u.get("ФИО", ""),
        "company": u.get("Компания/Проект", ""),
        "position": u.get("Должность", ""),
        "city": u.get("Город", ""),
        "phone": u.get("Телефон", ""),
        "sphere": u.get("Сфера", ""),
        "income": u.get("Доход", ""),
        "status": u.get("Статус", ""),
        "tier": _membership_tier(u),
        "registered": u.get("Дата регистрации", ""),
        "consent": (u.get("Согласие ПДн") or "").strip(),
        "balance": balances.get(tid, 0),
        "signups": signup_counts.get(tid, 0),
        "avatar": _avatar_url(tid),
    }


def _paid_counts(signups: list) -> dict:
    counts = {}
    for s in signups:
        if s.get("Статус") == SIGNUP_STATUS_PAID:
            tid = str(s.get("telegram_id", ""))
            counts[tid] = counts.get(tid, 0) + 1
    return counts


def _event_stats(signups: list) -> dict:
    stats = {}
    for s in signups:
        eid = str(s.get("ID события", ""))
        item = stats.setdefault(eid, {"people": 0, "tickets": 0, "pending": 0, "cash": 0, "points": 0})
        status = s.get("Статус")
        if status == SIGNUP_STATUS_PAID:
            item["people"] += 1
            item["tickets"] += _int(s.get("Количество"), 1) or 1
            item["cash"] += _int(s.get("К оплате"))
            item["points"] += _int(s.get("Листики"))
        elif status == SIGNUP_STATUS_PENDING:
            item["pending"] += 1
    return stats


def _event_dict(e: dict, stats: dict, today: date) -> dict:
    d = _parse_date(e.get("Дата", ""))
    item = stats.get(str(e.get("id")), {"people": 0, "tickets": 0, "pending": 0, "cash": 0, "points": 0})
    return {
        "id": e["id"],
        "title": e.get("Название", ""),
        "description": e.get("Описание", ""),
        "date": e.get("Дата", ""),
        "time": e.get("Время", ""),
        "place": e.get("Место", ""),
        "price": e.get("Цена", ""),
        "price_nonresident": e.get("Цена нерезидент", ""),
        "photo": e.get("Фото", ""),
        "photo_dark": e.get("Фото темное", ""),
        "past": bool(d and d < today),
        "free": _is_free_price(e.get("Цена", "")),
        **item,
    }


# --- Дашборд -----------------------------------------------------------------


@admin.route("/api/dashboard")
@admin_required
def dashboard():
    users = sheets.list_users()
    events = sheets.admin_list_events()
    signups = sheets.list_signups_all()
    balances = sheets.points_balances()
    today = date.today()

    counts = {"resident": 0, "non_resident": 0, "pending": 0}
    for u in users:
        counts[_membership_tier(u)] += 1

    stats = _event_stats(signups)
    upcoming = sorted(
        (_event_dict(e, stats, today) for e in events),
        key=lambda e: e["date"],
    )
    upcoming = [e for e in upcoming if not e["past"]][:8]

    by_id = {str(u.get("telegram_id")): u for u in users}
    pending_users = sorted(
        (u for u in users if _membership_tier(u) == "pending"),
        key=lambda u: u.get("Дата регистрации", ""), reverse=True,
    )[:8]
    titles = {str(e["id"]): e.get("Название", "") for e in events}
    recent = sorted(
        (s for s in signups if s.get("Статус") == SIGNUP_STATUS_PAID),
        key=lambda s: s.get("Дата записи", ""), reverse=True,
    )[:8]
    return jsonify({
        "counts": counts,
        "total_users": len(users),
        "points_in_circulation": sum(v for v in balances.values() if v > 0),
        "upcoming": upcoming,
        "pending": [_user_brief(u, balances, {}) for u in pending_users],
        "recent_signups": [
            {
                "fio": by_id.get(str(s.get("telegram_id")), {}).get("ФИО", "—"),
                "telegram_id": str(s.get("telegram_id")),
                "event": titles.get(str(s.get("ID события")), f"#{s.get('ID события')}"),
                "date": s.get("Дата записи", ""),
                "quantity": _int(s.get("Количество"), 1) or 1,
            }
            for s in recent
        ],
    })


# --- Люди --------------------------------------------------------------------


@admin.route("/api/users")
@admin_required
def users_list():
    users = sheets.list_users()
    balances = sheets.points_balances()
    counts = _paid_counts(sheets.list_signups_all())
    return jsonify({"users": [_user_brief(u, balances, counts) for u in users]})


def _find_user_or_404(telegram_id):
    for u in sheets.list_users():
        if str(u.get("telegram_id")) == str(telegram_id):
            return u
    return None


@admin.route("/api/users/<telegram_id>")
@admin_required
def user_detail(telegram_id):
    user = _find_user_or_404(telegram_id)
    if not user:
        return _err("not_found", "Человек не найден", 404)
    balances = sheets.points_balances()
    all_signups = sheets.list_signups_all()
    events = {str(e["id"]): e for e in sheets.admin_list_events()}
    users_by_id = {str(u.get("telegram_id")): u for u in sheets.list_users()}

    signups = []
    for s in all_signups:
        if str(s.get("telegram_id")) != str(telegram_id):
            continue
        e = events.get(str(s.get("ID события")), {})
        signups.append({
            "event_id": str(s.get("ID события")),
            "event": e.get("Название", f"(событие #{s.get('ID события')} удалено)"),
            "event_date": e.get("Дата", ""),
            "status": s.get("Статус", ""),
            "quantity": _int(s.get("Количество"), 1) or 1,
            "cash": _int(s.get("К оплате")),
            "points": _int(s.get("Листики")),
            "promo": s.get("Промокод", ""),
            "created": s.get("Дата записи", ""),
        })
    signups.sort(key=lambda s: s["created"], reverse=True)

    referrals = sheets.list_referrals()
    invited_by = None
    invited = []
    for r in referrals:
        if str(r.get("telegram_id")) == str(telegram_id):
            ref = users_by_id.get(str(r.get("Пригласил")), {})
            invited_by = {"telegram_id": str(r.get("Пригласил")), "fio": ref.get("ФИО", "—"), "rewarded": (r.get("Награда") or "").strip()}
        if str(r.get("Пригласил")) == str(telegram_id):
            who = users_by_id.get(str(r.get("telegram_id")), {})
            invited.append({
                "telegram_id": str(r.get("telegram_id")), "fio": who.get("ФИО", "— (анкету не заполнил)"),
                "status": who.get("Статус", ""), "rewarded": (r.get("Награда") or "").strip(),
            })

    visits = []
    for c in sheets.list_checkins(telegram_id=telegram_id):
        e = events.get(str(c.get("ID события")), {})
        visits.append({
            "event_id": str(c.get("ID события")),
            "event": e.get("Название", f"(событие #{c.get('ID события')} удалено)"),
            "event_date": e.get("Дата", ""),
            "time": c.get("Время", ""),
            "method": c.get("Способ", ""),
        })
    visits.sort(key=lambda v: v["time"], reverse=True)

    brief = _user_brief(user, balances, _paid_counts(all_signups))
    # списком, а не словарём: Flask сортирует ключи JSON по алфавиту, а поля
    # анкеты нужны в порядке самой анкеты (ФИО первым)
    fields = [{"name": h, "value": user.get(h, "")} for h in USER_EDITABLE]
    return jsonify({
        "user": brief,
        "fields": fields,
        "sb_id": user.get("sb_id", ""),
        "ledger": sheets.list_points_ledger(telegram_id, 100),
        "signups": signups,
        "visits": visits,
        "invited_by": invited_by,
        "invited": invited,
        "achievements": [
            {"title": a.get("Название", ""), "description": a.get("Описание", ""), "date": a.get("Дата", "")}
            for a in sheets.list_achievements_for_user(telegram_id)
        ],
    })


@admin.route("/api/users/<telegram_id>", methods=["PATCH"])
@admin_required
def user_update(telegram_id):
    data = request.get_json(silent=True) or {}
    user = _find_user_or_404(telegram_id)
    if not user:
        return _err("not_found", "Человек не найден", 404)
    values = {}
    for header in USER_EDITABLE:
        if header in data:
            value = str(data[header] or "").strip()[:1000]
            if header == "ФИО" and not value:
                return _err("bad_fio", "ФИО не может быть пустым")
            if value != (user.get(header) or ""):
                values[header] = value
    if not values:
        return jsonify({"status": "ok", "changed": 0})
    sheets.update_user_fields(telegram_id, values)
    changes = "; ".join(f"{k}: «{(user.get(k) or '')[:40]}» → «{v[:40]}»" for k, v in values.items())
    _log("Правка анкеты", f"{user.get('ФИО', '')} ({telegram_id})", changes)
    return jsonify({"status": "ok", "changed": len(values)})


@admin.route("/api/users/<telegram_id>/status", methods=["POST"])
@admin_required
def user_status(telegram_id):
    data = request.get_json(silent=True) or {}
    status = str(data.get("status") or "").strip()
    if status not in STATUSES:
        return _err("bad_status", "Неизвестный статус")
    user = _find_user_or_404(telegram_id)
    if not user:
        return _err("not_found", "Человек не найден", 404)
    before = user.get("Статус", "")
    if before != status:
        sheets.update_user_fields(telegram_id, {"Статус": status})
        _log("Смена статуса", f"{user.get('ФИО', '')} ({telegram_id})", f"{before or '—'} → {status}")
        if status in (STATUS_NON_RESIDENT, STATUS_RESIDENT):
            # Одобрили анкету — пригласившему положена награда (один раз, идемпотентно).
            _reward_referrer(telegram_id)
    return jsonify({"status": "ok", "new": status})


@admin.route("/api/users/<telegram_id>", methods=["DELETE"])
@admin_required
def user_delete(telegram_id):
    user = _find_user_or_404(telegram_id)
    if not user:
        return _err("not_found", "Человек не найден", 404)
    sheets.delete_user(telegram_id)
    _log("Удалена анкета", f"{user.get('ФИО', '')} ({telegram_id})", f"статус был: {user.get('Статус', '')}")
    return jsonify({"status": "ok"})


@admin.route("/api/users/<telegram_id>/points", methods=["POST"])
@admin_required
def user_points(telegram_id):
    data = request.get_json(silent=True) or {}
    amount = _int(data.get("amount"))
    reason = _str(data, "reason", 120)
    if amount == 0 or abs(amount) > 1_000_000:
        return _err("bad_amount", "Укажите сумму (не ноль, не больше 1 000 000)")
    if not reason:
        return _err("bad_reason", "Укажите причину")
    user = _find_user_or_404(telegram_id)
    if not user:
        return _err("not_found", "Человек не найден", 404)
    balance = sheets.get_points_balance(telegram_id, fresh=True)
    if balance + amount < 0:
        return _err("insufficient", f"На балансе только {balance} — столько списать нельзя")
    sheets.add_points(telegram_id, amount, reason, f"admin:{g.admin}")
    _log("Дубики", f"{user.get('ФИО', '')} ({telegram_id})", f"{amount:+d} — {reason} (баланс {balance} → {balance + amount})")
    return jsonify({"status": "ok", "balance": balance + amount})


@admin.route("/api/users/<telegram_id>/achievements", methods=["POST"])
@admin_required
def achievement_add(telegram_id):
    data = request.get_json(silent=True) or {}
    title = _str(data, "title", 80)
    if not title:
        return _err("bad_title", "Укажите название")
    user = _find_user_or_404(telegram_id)
    if not user:
        return _err("not_found", "Человек не найден", 404)
    when = _iso_date(data.get("date")) or date.today().strftime("%Y-%m-%d")
    sheets.add_achievement(telegram_id, title, _str(data, "description", 200), when)
    _log("Достижение +", f"{user.get('ФИО', '')} ({telegram_id})", title)
    return jsonify({"status": "ok"})


@admin.route("/api/users/<telegram_id>/achievements", methods=["DELETE"])
@admin_required
def achievement_delete(telegram_id):
    data = request.get_json(silent=True) or {}
    title, when = _str(data, "title", 80), _str(data, "date", 20)
    if not sheets.delete_achievement(telegram_id, title, when):
        return _err("not_found", "Достижение не найдено", 404)
    _log("Достижение −", str(telegram_id), title)
    return jsonify({"status": "ok"})


@admin.route("/api/users/<telegram_id>/avatar", methods=["POST"])
@admin_required
def user_avatar(telegram_id):
    user = _find_user_or_404(telegram_id)
    if not user:
        return _err("not_found", "Человек не найден", 404)
    file = request.files.get("photo")
    if not file:
        return _err("no_file", "Выберите фото")
    try:
        avatar_client.save_avatar(telegram_id, file.stream)
    except ValueError:
        return _err("invalid_image", "Файл не похож на изображение")
    sheets.set_avatar_url(telegram_id, _absolute_avatar_url(telegram_id))
    _log("Новое фото", f"{user.get('ФИО', '')} ({telegram_id})")
    return jsonify({"status": "ok", "avatar": _avatar_url(telegram_id)})


@admin.route("/api/export/users.csv")
@admin_required
def export_users():
    users = sheets.list_users()
    balances = sheets.points_balances()
    header = ["telegram_id", "username"] + [h for h in USERS_HEADERS if h not in ("telegram_id", "username")] + ["Баланс дубиков"]
    rows = [
        [u.get(h, "") for h in header[:-1]] + [balances.get(str(u.get("telegram_id")), 0)]
        for u in users
    ]
    _log("Экспорт", "люди", f"{len(rows)} строк")
    return _csv_response(f"banya-users-{date.today()}.csv", header, rows)


# --- Афиша -------------------------------------------------------------------


@admin.route("/api/events")
@admin_required
def events_list():
    stats = _event_stats(sheets.list_signups_all())
    today = date.today()
    events = [_event_dict(e, stats, today) for e in sheets.admin_list_events()]
    events.sort(key=lambda e: e["date"], reverse=True)
    return jsonify({"events": events})


def _clean_event(data: dict):
    """-> (значения для листа, None) или (None, (код, сообщение))."""
    title = _str(data, "title", 120)
    if not title:
        return None, ("bad_title", "Укажите название")
    when = _iso_date(data.get("date"))
    if not when:
        return None, ("bad_date", "Укажите дату (ГГГГ-ММ-ДД или ДД.ММ.ГГГГ)")
    try:
        price = _norm_price(data.get("price"))
        price_non = _norm_price(data.get("price_nonresident"))
    except ValueError as exc:
        return None, ("bad_price", f"Не понимаю цену «{exc}»: напишите число или «Бесплатно»")
    photo, photo_dark = _str(data, "photo", 300), _str(data, "photo_dark", 300)
    if not _safe_path(photo) or not _safe_path(photo_dark):
        return None, ("bad_photo", "Ссылка на фото должна начинаться с /static/ или https://")
    return {
        "Название": title,
        "Описание": _str(data, "description", 1000),
        "Дата": when,
        "Время": _str(data, "time", 40),
        "Место": _str(data, "place", 160),
        "Цена": price,
        "Цена нерезидент": price_non,
        "Фото": photo,
        "Фото темное": photo_dark,
    }, None


@admin.route("/api/events", methods=["POST"])
@admin_required
def event_create():
    values, error = _clean_event(request.get_json(silent=True) or {})
    if error:
        return _err(*error)
    record = sheets.add_event(values)
    _log("Событие +", f"#{record['id']} {values['Название']}", f"{values['Дата']} {values['Время']}; цена {values['Цена'] or '—'} / {values['Цена нерезидент'] or '—'}")
    return jsonify({"status": "ok", "id": record["id"]})


@admin.route("/api/events/<event_id>", methods=["PUT"])
@admin_required
def event_update(event_id):
    values, error = _clean_event(request.get_json(silent=True) or {})
    if error:
        return _err(*error)
    before = next((e for e in sheets.admin_list_events() if str(e["id"]) == str(event_id)), None)
    if not before or not sheets.update_event(event_id, values):
        return _err("not_found", "Событие не найдено", 404)
    changes = "; ".join(
        f"{k}: «{(before.get(k) or '')[:40]}» → «{v[:40]}»" for k, v in values.items() if (before.get(k) or "") != v
    )
    _log("Событие ✎", f"#{event_id} {values['Название']}", changes or "без изменений")
    return jsonify({"status": "ok"})


@admin.route("/api/events/<event_id>", methods=["DELETE"])
@admin_required
def event_delete(event_id):
    before = next((e for e in sheets.admin_list_events() if str(e["id"]) == str(event_id)), None)
    if not before:
        return _err("not_found", "Событие не найдено", 404)
    live = [
        s for s in sheets.list_signups_all()
        if str(s.get("ID события")) == str(event_id) and s.get("Статус") in (SIGNUP_STATUS_PAID, SIGNUP_STATUS_PENDING)
    ]
    if live:
        return _err("has_signups", f"Нельзя удалить: есть записи ({len(live)}). Сначала отмените их.", 409)
    sheets.delete_event(event_id)
    _log("Событие −", f"#{event_id} {before.get('Название', '')}", before.get("Дата", ""))
    return jsonify({"status": "ok"})


def _event_signup_rows(event_id: str) -> list:
    users = {str(u.get("telegram_id")): u for u in sheets.list_users()}
    checks = {c["telegram_id"]: c for c in sheets.list_checkins(event_id=event_id)}
    rows = []
    seen = set()
    for s in sheets.list_signups_all():
        if str(s.get("ID события")) != str(event_id):
            continue
        tid = str(s.get("telegram_id"))
        seen.add(tid)
        u = users.get(tid, {})
        check = checks.get(tid, {})
        rows.append({
            "telegram_id": tid,
            "fio": u.get("ФИО", "— (анкета удалена)"),
            "username": u.get("username", ""),
            "phone": u.get("Телефон", ""),
            "tier": _membership_tier(u) if u else "pending",
            "status": s.get("Статус", ""),
            "quantity": _int(s.get("Количество"), 1) or 1,
            "cash": _int(s.get("К оплате")),
            "points": _int(s.get("Листики")),
            "promo": s.get("Промокод", ""),
            "created": s.get("Дата записи", ""),
            "order": s.get("Заказ", ""),
            "checked_in": check.get("Время", ""),
            "checkin_method": check.get("Способ", ""),
        })
    rows.sort(key=lambda r: r["created"])
    # отмеченные на входе без записи на это событие (пришли «с улицы» / записал админ вручную)
    for tid, check in checks.items():
        if tid in seen:
            continue
        u = users.get(tid, {})
        rows.append({
            "telegram_id": tid, "fio": u.get("ФИО", "— (анкета удалена)"), "username": u.get("username", ""),
            "phone": u.get("Телефон", ""), "tier": _membership_tier(u) if u else "pending",
            "status": "без записи", "quantity": 1, "cash": 0, "points": 0, "promo": "", "created": "", "order": "",
            "checked_in": check.get("Время", ""), "checkin_method": check.get("Способ", ""),
        })
    return rows


@admin.route("/api/events/<event_id>/signups")
@admin_required
def event_signups(event_id):
    return jsonify({"signups": _event_signup_rows(event_id)})


@admin.route("/api/events/<event_id>/signups", methods=["POST"])
@admin_required
def event_signup_add(event_id):
    data = request.get_json(silent=True) or {}
    telegram_id = _str(data, "telegram_id", 30)
    quantity = _int(data.get("quantity"), 1)
    if not 1 <= quantity <= 20:
        return _err("bad_quantity", "Количество билетов — от 1 до 20")
    event = next((e for e in sheets.admin_list_events() if str(e["id"]) == str(event_id)), None)
    if not event:
        return _err("not_found", "Событие не найдено", 404)
    user = _find_user_or_404(telegram_id)
    if not user:
        return _err("no_user", "Такого человека нет в базе")
    if sheets.is_signed_up(telegram_id, event_id):
        return _err("already", "Этот человек уже записан")
    sheets.admin_add_signup(telegram_id, event_id, quantity)
    _log("Запись +", f"{event.get('Название', '')} (#{event_id})", f"{user.get('ФИО', '')} ({telegram_id}), билетов: {quantity}")
    return jsonify({"status": "ok"})


@admin.route("/api/events/<event_id>/signups/<telegram_id>", methods=["DELETE"])
@admin_required
def event_signup_cancel(event_id, telegram_id):
    record = sheets.cancel_signup(telegram_id, event_id)
    if not record:
        return _err("not_found", "Запись не найдена", 404)
    user = _find_user_or_404(telegram_id) or {}
    refunded = _int(record.get("Листики"))
    _log(
        "Запись −", f"событие #{event_id}",
        f"{user.get('ФИО', telegram_id)} ({telegram_id}); дубиков возвращено: {refunded}; деньги {_int(record.get('К оплате'))} ₽ — вручную в Продамусе",
    )
    return jsonify({"status": "ok", "refunded_points": refunded, "cash": _int(record.get("К оплате"))})


@admin.route("/api/events/<event_id>/export.csv")
@admin_required
def export_event(event_id):
    rows = _event_signup_rows(event_id)
    header = ["ФИО", "telegram_id", "username", "Телефон", "Статус записи", "Билетов", "Оплачено деньгами, ₽", "Дубиков", "Промокод", "Дата записи", "Пришёл (время отметки)"]
    data = [[r["fio"], r["telegram_id"], r["username"], r["phone"], r["status"], r["quantity"], r["cash"], r["points"], r["promo"], r["created"], r["checked_in"]] for r in rows]
    _log("Экспорт", f"записи события #{event_id}", f"{len(data)} строк")
    return _csv_response(f"banya-event-{event_id}.csv", header, data)


# --- Загрузка картинок -------------------------------------------------------


@admin.route("/api/upload/event-cover", methods=["POST"])
@admin_required
def upload_event_cover():
    file = request.files.get("file")
    if not file:
        return _err("no_file", "Выберите файл")
    mode = request.form.get("mode", "cover")
    try:
        if mode in ("cover", "poster"):
            result = image_tools.save_event_cover(file.stream, poster=(mode == "poster"))
        elif mode == "light":
            result = {"photo": image_tools.save_event_photo_only(file.stream, dark=False)}
        elif mode == "dark":
            result = {"photo_dark": image_tools.save_event_photo_only(file.stream, dark=True)}
        else:
            return _err("bad_mode", "Неизвестный режим")
    except ValueError:
        return _err("invalid_image", "Файл не похож на изображение")
    return jsonify(result)


@admin.route("/api/upload/material-cover", methods=["POST"])
@admin_required
def upload_material_cover():
    file = request.files.get("file")
    if not file:
        return _err("no_file", "Выберите файл")
    try:
        return jsonify({"photo": image_tools.save_material_cover(file.stream)})
    except ValueError:
        return _err("invalid_image", "Файл не похож на изображение")


# --- Промокоды ---------------------------------------------------------------


def _promo_dict(p: dict, uses: dict) -> dict:
    code = (p.get("Код") or "").strip()
    return {
        "code": code,
        "type": (p.get("Тип") or "").strip(),
        "size": p.get("Размер", ""),
        "events": (p.get("События") or "").strip() or "все",
        "limit": (p.get("Лимит") or "").strip(),
        "until": (p.get("Действует до") or "").strip(),
        "active": (p.get("Активен") or "").strip().casefold() not in ("нет", "no", "false", "0"),
        "uses": uses.get(code.casefold(), 0),
    }


@admin.route("/api/promo")
@admin_required
def promo_list():
    uses = sheets.promo_usage_map()
    return jsonify({"promos": [_promo_dict(p, uses) for p in sheets.list_promos()]})


def _clean_promo(data: dict, code: str):
    kind = _str(data, "type", 20)
    if kind not in (PROMO_TYPE_PERCENT, PROMO_TYPE_RUB):
        return None, ("bad_type", "Тип — «процент» или «рубли»")
    size = _to_float(data.get("size"))
    if size <= 0 or (kind == PROMO_TYPE_PERCENT and size > 100):
        return None, ("bad_size", "Размер: процент — от 1 до 100, рубли — больше нуля")
    scope = _str(data, "events", 200).casefold()
    if scope in ("", "все", "all"):
        scope = "все"
    else:
        ids = [p for p in re.split(r"[,;\s]+", scope) if p]
        known = {str(e["id"]) for e in sheets.admin_list_events()}
        unknown = [i for i in ids if i not in known]
        if not ids or unknown:
            return None, ("bad_events", f"Нет событий с ID: {', '.join(unknown) or scope}")
        scope = ", ".join(ids)
    limit_raw = _str(data, "limit", 10)
    if limit_raw and (not limit_raw.isdigit() or int(limit_raw) < 1):
        return None, ("bad_limit", "Лимит — целое число от 1 (или пусто = без ограничений)")
    until_raw = _str(data, "until", 20)
    until = _iso_date(until_raw) if until_raw else ""
    if until_raw and not until:
        return None, ("bad_until", "Дата окончания — ГГГГ-ММ-ДД или пусто")
    size_text = str(int(size)) if size == int(size) else str(size)
    return {
        "Код": code, "Тип": kind, "Размер": size_text, "События": scope, "Лимит": limit_raw,
        "Действует до": until, "Активен": "да" if data.get("active", True) else "нет",
    }, None


@admin.route("/api/promo", methods=["POST"])
@admin_required
def promo_create():
    data = request.get_json(silent=True) or {}
    code = _str(data, "code", 32)
    if not re.fullmatch(r"[\w\-]{2,32}", code):
        return _err("bad_code", "Код — 2–32 символа: буквы, цифры, «-» и «_»")
    if sheets.find_promo(code, fresh=True):
        return _err("exists", "Такой код уже есть")
    values, error = _clean_promo(data, code)
    if error:
        return _err(*error)
    sheets.add_promo(values)
    _log("Промокод +", code, f"{values['Тип']} {values['Размер']}; события: {values['События']}; лимит {values['Лимит'] or '∞'}; до {values['Действует до'] or '∞'}")
    return jsonify({"status": "ok"})


@admin.route("/api/promo/<code>", methods=["PUT"])
@admin_required
def promo_update(code):
    if not sheets.find_promo(code, fresh=True):
        return _err("not_found", "Код не найден", 404)
    values, error = _clean_promo(request.get_json(silent=True) or {}, code)
    if error:
        return _err(*error)
    values.pop("Код")
    sheets.update_promo(code, values)
    _log("Промокод ✎", code, f"{values['Тип']} {values['Размер']}; события: {values['События']}; лимит {values['Лимит'] or '∞'}; до {values['Действует до'] or '∞'}; активен: {values['Активен']}")
    return jsonify({"status": "ok"})


@admin.route("/api/promo/<code>", methods=["DELETE"])
@admin_required
def promo_delete(code):
    if not sheets.delete_promo(code):
        return _err("not_found", "Код не найден", 404)
    _log("Промокод −", code)
    return jsonify({"status": "ok"})


# --- Материалы ---------------------------------------------------------------


@admin.route("/api/materials")
@admin_required
def materials_list():
    return jsonify({"materials": [
        {
            "row": m["id"], "title": m.get("Название", ""), "description": m.get("Описание", ""),
            "link": m.get("Ссылка", ""), "category": m.get("Категория", ""),
            "date": m.get("Дата публикации", ""), "photo": m.get("Фото", ""),
        }
        for m in sheets.list_materials()
    ]})


def _clean_material(data: dict):
    title = _str(data, "title", 150)
    if not title:
        return None, ("bad_title", "Укажите название")
    link = _str(data, "link", 400)
    if link and urlparse(link).scheme not in ("http", "https"):
        return None, ("bad_link", "Ссылка должна начинаться с http:// или https://")
    photo = _str(data, "photo", 300)
    if not _safe_path(photo):
        return None, ("bad_photo", "Ссылка на фото должна начинаться с /static/ или https://")
    when_raw = _str(data, "date", 20)
    when = _iso_date(when_raw) if when_raw else date.today().strftime("%Y-%m-%d")
    if when_raw and not when:
        return None, ("bad_date", "Дата — ГГГГ-ММ-ДД")
    return {
        "Название": title, "Описание": _str(data, "description", 600), "Ссылка": link,
        "Категория": _str(data, "category", 60), "Дата публикации": when, "Фото": photo,
    }, None


@admin.route("/api/materials", methods=["POST"])
@admin_required
def material_create():
    values, error = _clean_material(request.get_json(silent=True) or {})
    if error:
        return _err(*error)
    sheets.add_material(values)
    _log("Материал +", values["Название"], values["Ссылка"])
    return jsonify({"status": "ok"})


@admin.route("/api/materials/<int:row>", methods=["PUT"])
@admin_required
def material_update(row):
    data = request.get_json(silent=True) or {}
    values, error = _clean_material(data)
    if error:
        return _err(*error)
    if not sheets.update_material(row, _str(data, "expect_title", 150), values):
        return _err("stale", "Таблица изменилась — обновите страницу и повторите", 409)
    _log("Материал ✎", values["Название"], values["Ссылка"])
    return jsonify({"status": "ok"})


@admin.route("/api/materials/<int:row>", methods=["DELETE"])
@admin_required
def material_delete(row):
    data = request.get_json(silent=True) or {}
    title = _str(data, "expect_title", 150)
    if not sheets.delete_material(row, title):
        return _err("stale", "Таблица изменилась — обновите страницу и повторите", 409)
    _log("Материал −", title)
    return jsonify({"status": "ok"})


# --- Дубики и журнал ---------------------------------------------------------


@admin.route("/api/points")
@admin_required
def points_all():
    users = {str(u.get("telegram_id")): u.get("ФИО", "") for u in sheets.list_users()}
    items = sheets.list_points_ledger(None, 300)
    for item in items:
        item["fio"] = users.get(item["telegram_id"], "—")
    balances = sheets.points_balances()
    return jsonify({"items": items, "total": sum(v for v in balances.values() if v > 0)})


@admin.route("/api/log")
@admin_required
def log_list():
    return jsonify({"items": sheets.list_admin_log(300)})


# --- Чекер: отметка прихода на мероприятие ----------------------------------


def _checkin_card(user: dict) -> dict:
    tid = str(user.get("telegram_id", ""))
    return {
        "telegram_id": tid,
        "fio": user.get("ФИО", ""),
        "company": user.get("Компания/Проект", ""),
        "position": user.get("Должность", ""),
        "username": user.get("username", ""),
        "tier": _membership_tier(user),
        "status": user.get("Статус", ""),
        "avatar": _avatar_url(tid),
    }


@admin.route("/api/checkin", methods=["POST"])
@admin_required
def checkin():
    """Отмечает приход человека на событие. Человек задаётся кодом из его QR
    (code) или вручную (telegram_id). Ответ status:
      ok         — отметили;
      already    — уже был отмечен раньше (time — когда);
      no_signup  — на это событие у человека нет оплаченной записи: не отмечаем,
                   пока админ не подтвердит (повтор с force=true)."""
    data = request.get_json(silent=True) or {}
    event_id = _str(data, "event_id", 20)
    event = next((e for e in sheets.admin_list_events() if str(e["id"]) == event_id), None)
    if not event:
        return _err("not_found", "Событие не найдено", 404)

    code = _str(data, "code", 100)
    if code:
        telegram_id = checkin_tokens.parse_code(code)
        if not telegram_id:
            return _err("bad_code", "Это не QR-код Банного Ордена (или код повреждён)")
        method = "QR"
    else:
        telegram_id = _str(data, "telegram_id", 30)
        method = "вручную"
    user = _find_user_or_404(telegram_id)
    if not user:
        return _err("no_user", "Человека с этим кодом нет в базе", 404)
    card = _checkin_card(user)

    existing = sheets.get_checkin(telegram_id, event_id)
    if existing:
        return jsonify({"status": "already", "user": card, "time": existing.get("Время", "")})

    quantity = sheets.get_signup_quantity(telegram_id, event_id)
    walk_in = quantity == 0
    if walk_in and not data.get("force"):
        return jsonify({"status": "no_signup", "user": card})

    when = sheets.add_checkin(telegram_id, event_id, g.admin, method + (", без записи" if walk_in else ""))
    _log("Отметка прихода", f"{event.get('Название', '')} (#{event_id})", f"{user.get('ФИО', '')} ({telegram_id}) · {method}{' · без записи' if walk_in else ''}")
    return jsonify({"status": "ok", "user": card, "quantity": max(quantity, 1), "walk_in": walk_in, "time": when})


@admin.route("/api/checkin/<event_id>/<telegram_id>", methods=["DELETE"])
@admin_required
def checkin_undo(event_id, telegram_id):
    record = sheets.remove_checkin(telegram_id, event_id)
    if not record:
        return _err("not_found", "Отметки нет", 404)
    user = _find_user_or_404(telegram_id) or {}
    _log("Отметка снята", f"событие #{event_id}", f"{user.get('ФИО', telegram_id)} ({telegram_id}); было {record.get('Время', '')}")
    return jsonify({"status": "ok"})
