from datetime import datetime

from flask import Blueprint, jsonify, request, session

import sheets_client as sheets
import telegram_auth
from config import Config
from constants import ONBOARDING_STEPS, STATUS_ACTIVE

api = Blueprint("api", __name__, url_prefix="/api")

_STEPS_BY_KEY = {step["key"]: step for step in ONBOARDING_STEPS}


def _current_telegram_id():
    return session.get("telegram_id")


def _is_active(user) -> bool:
    if not user:
        return False
    return (user.get("Статус") or "").strip().casefold() == STATUS_ACTIVE.casefold()


def _public_user(user: dict) -> dict:
    return {
        "fio": user.get("ФИО", ""),
        "dob": user.get("Дата рождения", ""),
        "company": user.get("Компания/Проект", ""),
        "sphere": user.get("Сфера", ""),
        "role": user.get("Роль", ""),
        "request": user.get("Запрос", ""),
        "offer": user.get("Предложение", ""),
        "source": user.get("Как узнал", ""),
        "status": user.get("Статус", ""),
        "is_active": _is_active(user),
    }


def _parse_date(value: str):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _resolve_option_label(step_key: str, value, other_text: str) -> str:
    if value == "other":
        return (other_text or "").strip() or "Другое"
    step = _STEPS_BY_KEY[step_key]
    for opt in step["options"]:
        if opt["value"] == value:
            return opt["label"]
    return str(value or "")


def _resolve_multi_labels(step_key: str, values, other_text: str) -> str:
    if not isinstance(values, list):
        return ""
    labels = [_resolve_option_label(step_key, v, other_text) for v in values]
    return ", ".join(label for label in labels if label)


@api.route("/auth", methods=["POST"])
def auth():
    data = request.get_json(silent=True) or {}
    init_data = data.get("initData", "")
    dev_id = request.args.get("dev_id")

    if Config.DEV_MODE and dev_id:
        telegram_id = dev_id
        username = f"dev_{dev_id}"
    else:
        parsed = telegram_auth.validate_init_data(init_data, Config.BOT_TOKEN)
        if not parsed:
            return jsonify({"error": "invalid_init_data"}), 401
        telegram_id = parsed["telegram_id"]
        username = parsed.get("username")

    session["telegram_id"] = str(telegram_id)
    session["username"] = username

    user = sheets.find_user(telegram_id)
    if not user:
        return jsonify({"status": "new", "steps": ONBOARDING_STEPS})
    return jsonify({"status": "active", "user": _public_user(user)})


@api.route("/onboarding-config", methods=["GET"])
def onboarding_config():
    return jsonify({"steps": ONBOARDING_STEPS})


@api.route("/register", methods=["POST"])
def register():
    telegram_id = _current_telegram_id()
    if not telegram_id:
        return jsonify({"error": "unauthorized"}), 401

    if sheets.find_user(telegram_id):
        return jsonify({"error": "already_registered"}), 400

    data = request.get_json(silent=True) or {}
    fio = (data.get("fio") or "").strip()
    dob = (data.get("dob") or "").strip()
    company = (data.get("company") or "").strip()
    sphere_values = data.get("sphere") or []
    sphere_other = data.get("sphere_other", "")
    role_value = data.get("role")
    role_other = data.get("role_other", "")
    request_values = data.get("request") or []
    offer = (data.get("offer") or "").strip()
    source_value = data.get("source")
    source_other = data.get("source_other", "")
    referrer = (data.get("referrer") or "").strip()

    if not (fio and dob and company and sphere_values and role_value and request_values and offer and source_value):
        return jsonify({"error": "missing_fields"}), 400

    sphere = _resolve_multi_labels("sphere", sphere_values, sphere_other)
    role = _resolve_option_label("role", role_value, role_other)
    request_text = _resolve_multi_labels("request", request_values, "")
    source = _resolve_option_label("source", source_value, source_other)
    if source_value == "recommendation" and referrer:
        source = f"{source} ({referrer})"

    sheets.create_user(telegram_id, session.get("username"), fio, dob, company, sphere, role, request_text, offer, source)

    user = sheets.find_user(telegram_id)
    return jsonify({"status": "active", "user": _public_user(user)})


def _public_event(e: dict, is_registered: bool, can_signup: bool) -> dict:
    return {
        "id": e["id"],
        "title": e.get("Название", ""),
        "description": e.get("Описание", ""),
        "date": e.get("Дата", ""),
        "time": e.get("Время", ""),
        "place": e.get("Место", ""),
        "price": e.get("Цена", ""),
        "photo": e.get("Фото", ""),
        "is_registered": is_registered,
        "can_signup": can_signup,
    }


@api.route("/events", methods=["GET"])
def events():
    telegram_id = _current_telegram_id()
    if not telegram_id:
        return jsonify({"error": "unauthorized"}), 401

    user = sheets.find_user(telegram_id)
    can_signup = _is_active(user)

    events_list = sheets.list_events()
    signups = sheets.list_signups_for_user(telegram_id)
    signed_ids = {str(s.get("ID события")) for s in signups}

    result = [_public_event(e, str(e["id"]) in signed_ids, can_signup) for e in events_list]
    return jsonify({"events": result})


@api.route("/events/<int:event_id>", methods=["GET"])
def event_detail(event_id):
    telegram_id = _current_telegram_id()
    if not telegram_id:
        return jsonify({"error": "unauthorized"}), 401

    event = sheets.get_event(event_id)
    if not event:
        return jsonify({"error": "event_not_found"}), 404

    user = sheets.find_user(telegram_id)
    attendees = sheets.list_attendees(event_id)
    return jsonify(
        {
            "event": _public_event(event, sheets.is_signed_up(telegram_id, event_id), _is_active(user)),
            "attendees": attendees,
            "attendees_count": len(attendees),
        }
    )


@api.route("/events/<int:event_id>/signup", methods=["POST"])
def event_signup(event_id):
    telegram_id = _current_telegram_id()
    if not telegram_id:
        return jsonify({"error": "unauthorized"}), 401

    user = sheets.find_user(telegram_id)
    if not _is_active(user):
        return jsonify({"error": "inactive_member"}), 403

    event = sheets.get_event(event_id)
    if not event:
        return jsonify({"error": "event_not_found"}), 404
    if sheets.is_signed_up(telegram_id, event_id):
        return jsonify({"error": "already_registered"}), 400

    sheets.add_signup(telegram_id, event_id)
    return jsonify({"status": "ok"})


@api.route("/materials", methods=["GET"])
def materials():
    telegram_id = _current_telegram_id()
    if not telegram_id:
        return jsonify({"error": "unauthorized"}), 401

    items = sheets.list_materials()
    result = [
        {
            "id": m["id"],
            "title": m.get("Название", ""),
            "description": m.get("Описание", ""),
            "link": m.get("Ссылка", ""),
            "category": m.get("Категория", ""),
            "date": m.get("Дата публикации", ""),
        }
        for m in items
    ]
    return jsonify({"materials": result})


@api.route("/profile", methods=["GET"])
def profile():
    telegram_id = _current_telegram_id()
    if not telegram_id:
        return jsonify({"error": "unauthorized"}), 401

    user = sheets.find_user(telegram_id)
    if not user:
        return jsonify({"error": "user_not_found"}), 404

    signups = sheets.list_signups_for_user(telegram_id)
    events_by_id = {str(e["id"]): e for e in sheets.list_events()}
    today = datetime.now().date()

    upcoming, past = [], []
    for signup in signups:
        event = events_by_id.get(str(signup.get("ID события")))
        if not event:
            continue
        item = {
            "id": event["id"],
            "title": event.get("Название", ""),
            "date": event.get("Дата", ""),
            "place": event.get("Место", ""),
        }
        event_date = _parse_date(event.get("Дата", ""))
        if event_date and event_date < today:
            past.append(item)
        else:
            upcoming.append(item)

    achievements = [
        {
            "title": a.get("Название", ""),
            "description": a.get("Описание", ""),
            "date": a.get("Дата", ""),
        }
        for a in sheets.list_achievements_for_user(telegram_id)
    ]

    return jsonify(
        {
            "user": _public_user(user),
            "upcoming_events": upcoming,
            "past_events": past,
            "achievements": achievements,
        }
    )
