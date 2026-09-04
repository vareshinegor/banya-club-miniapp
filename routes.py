import re
import time
from datetime import datetime

from flask import Blueprint, jsonify, request, session

import prodamus_client
import sheets_client as sheets
import telegram_auth
import webhook_client
from config import Config
from constants import (
    MAX_TICKETS_PER_SIGNUP,
    ONBOARDING_STEPS,
    SIGNUP_STATUS_FAILED,
    SIGNUP_STATUS_PAID,
    STATUS_NON_RESIDENT,
    STATUS_RESIDENT,
)

api = Blueprint("api", __name__, url_prefix="/api")

_STEPS_BY_KEY = {step["key"]: step for step in ONBOARDING_STEPS}

_MONTHS_RU_NOM = [
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
]


def _current_telegram_id():
    return session.get("telegram_id")


def _membership_tier(user) -> str:
    """"resident" (оплаченная подписка) / "non_resident" (анкета одобрена, без
    подписки) / "pending" (анкета ещё не рассмотрена, либо статус пустой/
    неизвестный — по умолчанию считаем самым ограниченным уровнем)."""
    if not user:
        return "pending"
    status = (user.get("Статус") or "").strip().casefold()
    if status == STATUS_RESIDENT.casefold():
        return "resident"
    if status == STATUS_NON_RESIDENT.casefold():
        return "non_resident"
    return "pending"


def _can_signup(tier: str) -> bool:
    return tier in ("resident", "non_resident")


def _format_since(registered_at: str) -> str:
    if not registered_at:
        return ""
    try:
        dt = datetime.strptime(registered_at.strip()[:10], "%Y-%m-%d")
    except ValueError:
        return ""
    return f"{_MONTHS_RU_NOM[dt.month - 1]} {dt.year}"


def _public_user(user: dict) -> dict:
    return {
        "fio": user.get("ФИО", ""),
        "dob": user.get("Дата рождения", ""),
        "company": user.get("Компания/Проект", ""),
        "position": user.get("Должность", ""),
        "city": user.get("Город", ""),
        "phone": user.get("Телефон", ""),
        "telegram_username": user.get("username", ""),
        "sphere": user.get("Сфера", ""),
        "role": user.get("Роль", ""),
        "request": user.get("Запрос", ""),
        "offer": user.get("Предложение", ""),
        "source": user.get("Как узнал", ""),
        "status": user.get("Статус", ""),
        "status_tier": _membership_tier(user),
        "since": _format_since(user.get("Дата регистрации", "")),
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


def _parse_price_rub(price_str: str) -> float:
    """"8 500 ₽" -> 8500.0. Возвращает 0 если цену не удалось распознать."""
    if not price_str:
        return 0.0
    cleaned = re.sub(r"[^\d,.]", "", price_str).replace(",", ".")
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def _normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits


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
    field_values = {}
    missing = False

    for step in ONBOARDING_STEPS:
        key = step["key"]

        if step["type"] == "text":
            value = (data.get(key) or "").strip()
            if step.get("required") and not value:
                missing = True
            field_values[step["header"]] = value

        elif step["type"] == "fields":
            for f in step["fields"]:
                value = (data.get(f["key"]) or "").strip()
                if f.get("required") and not value:
                    missing = True
                field_values[f["header"]] = value

        elif step["type"] == "select":
            value = data.get(key)
            other = data.get(f"{key}_other", "")
            if step.get("required") and not value:
                missing = True
            elif value == "other" and not (other or "").strip():
                missing = True
            label = _resolve_option_label(key, value, other) if value else ""
            if key == "source" and value == "recommendation":
                referrer = (data.get("referrer") or "").strip()
                if referrer:
                    label = f"{label} ({referrer})"
            field_values[step["header"]] = label

        elif step["type"] == "multiselect":
            values = data.get(key) or []
            other = data.get(f"{key}_other", "")
            if step.get("required") and not values:
                missing = True
            elif "other" in values and not (other or "").strip():
                missing = True
            field_values[step["header"]] = _resolve_multi_labels(key, values, other)

    if missing:
        return jsonify({"error": "missing_fields"}), 400

    sb_id = sheets.find_platform_id(telegram_id) or ""
    sheets.create_user(telegram_id, session.get("username"), sb_id, field_values)

    try:
        # Схема ключей задана стороной vakas-tools — менять только по согласованию с ними.
        webhook_client.send_application({
            "ss_id": sb_id,
            "client_id": sb_id,
            "name": field_values.get("ФИО", ""),
            "phone": field_values.get("Телефон", ""),
            "email": "",
            "utm_source": "",
            "utm_medium": "",
            "utm_campaign": "",
            "birthday": field_values.get("Дата рождения", ""),
            "company": field_values.get("Компания/Проект", ""),
            "dohod": field_values.get("Доход", ""),
            "impact": field_values.get("Предложение", ""),
            "nisha": field_values.get("Сфера", ""),
            "zapros": field_values.get("Запрос", ""),
            "rolework": field_values.get("Роль", ""),
            "otkuda": field_values.get("Как узнал", ""),
            "phio": field_values.get("ФИО", ""),
            "import": "update",
        })
    except Exception as exc:  # вебхук недоступен/не настроен — заявка в клуб всё равно должна пройти
        print(f"[webhook] не удалось отправить заявку: {exc}")

    user = sheets.find_user(telegram_id)
    return jsonify({"status": "active", "user": _public_user(user)})


@api.route("/webhooks/salebot", methods=["POST"])
def salebot_webhook():
    """Входящий вебхук от сейлбота. Не требует Telegram-сессии — это серверный
    вызов от другого бота, а не от мини-аппа.

    В реальных запросах от salebot их поле "telegram_id" всегда пустое, а
    telegram-id пользователя приходит в поле "platform_id"; их собственный
    внутренний ID клиента (наш sb_id) приходит в поле "client_id". Оставляем
    также поддержку "телеграм_id"/"platform_id" как sb_id на случай, если
    salebot когда-нибудь начнёт слать поля правильно названными."""
    secret = Config.INCOMING_WEBHOOK_SECRET
    if secret and request.args.get("token") != secret:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    telegram_id = data.get("platform_id") or data.get("telegram_id")
    sb_id = data.get("client_id") or data.get("sb_id")
    if not telegram_id or not sb_id:
        return jsonify({"error": "missing_fields"}), 400

    sheets.save_platform_id(telegram_id, sb_id)
    return jsonify({"status": "ok"})


@api.route("/webhooks/salebot/subscription", methods=["POST"])
def salebot_subscription_webhook():
    """Вебхук от salebot ПОСЛЕ того как человек реально оплатил подписку —
    оплата подписки проходит на их стороне, не через наш Продамус (тот
    оформляет только разовую оплату конкретной бани). Переводит пользователя
    в STATUS_RESIDENT. Не требует Telegram-сессии — серверный вызов от salebot."""
    secret = Config.INCOMING_WEBHOOK_SECRET
    if secret and request.args.get("token") != secret:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    telegram_id = data.get("tg_id") or data.get("telegram_id") or data.get("platform_id")
    sb_id = data.get("sb_id") or data.get("client_id") or ""
    if not telegram_id:
        return jsonify({"error": "missing_fields"}), 400

    if not sheets.mark_subscription_paid(telegram_id, sb_id):
        return jsonify({"error": "user_not_found"}), 404
    return jsonify({"status": "ok"})


def _event_price_for_tier(event: dict, tier: str) -> str:
    """Нерезиденты видят "Цена нерезидент", если админ её заполнил — иначе
    (как и резиденты) обычную "Цена"."""
    if tier == "non_resident":
        non_resident_price = (event.get("Цена нерезидент") or "").strip()
        if non_resident_price:
            return non_resident_price
    return event.get("Цена", "")


def _public_event(e: dict, is_registered: bool, can_signup: bool, tier: str, registered_quantity: int = 0) -> dict:
    return {
        "id": e["id"],
        "title": e.get("Название", ""),
        "description": e.get("Описание", ""),
        "date": e.get("Дата", ""),
        "time": e.get("Время", ""),
        "place": e.get("Место", ""),
        "price": _event_price_for_tier(e, tier),
        "photo": e.get("Фото", ""),
        "is_registered": is_registered,
        "can_signup": can_signup,
        "registered_quantity": registered_quantity,
        "max_tickets": MAX_TICKETS_PER_SIGNUP,
    }


@api.route("/events", methods=["GET"])
def events():
    telegram_id = _current_telegram_id()
    if not telegram_id:
        return jsonify({"error": "unauthorized"}), 401

    user = sheets.find_user(telegram_id)
    tier = _membership_tier(user)
    can_signup = _can_signup(tier)

    events_list = sheets.list_events()
    signups = sheets.list_signups_for_user(telegram_id)
    quantity_by_event = {}
    for s in signups:
        try:
            quantity_by_event[str(s.get("ID события"))] = int(s.get("Количество") or 1)
        except ValueError:
            quantity_by_event[str(s.get("ID события"))] = 1

    result = [
        _public_event(e, str(e["id"]) in quantity_by_event, can_signup, tier, quantity_by_event.get(str(e["id"]), 0))
        for e in events_list
    ]
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
    tier = _membership_tier(user)
    attendees = sheets.list_attendees(event_id)
    registered_quantity = sheets.get_signup_quantity(telegram_id, event_id)
    return jsonify(
        {
            "event": _public_event(event, registered_quantity > 0, _can_signup(tier), tier, registered_quantity),
            "attendees": attendees,
            "attendees_count": sum(a.get("quantity", 1) for a in attendees),
        }
    )


@api.route("/events/<int:event_id>/signup", methods=["POST"])
def event_signup(event_id):
    """Не записывает сразу — создаёт запись со статусом "ожидает оплаты" и
    возвращает ссылку на оплату Продамуса. Реальной записью (is_signed_up)
    это становится только после вебхука с подтверждением платежа."""
    telegram_id = _current_telegram_id()
    if not telegram_id:
        return jsonify({"error": "unauthorized"}), 401

    user = sheets.find_user(telegram_id)
    tier = _membership_tier(user)
    if not _can_signup(tier):
        return jsonify({"error": "pending_review"}), 403

    event = sheets.get_event(event_id)
    if not event:
        return jsonify({"error": "event_not_found"}), 404
    if sheets.is_signed_up(telegram_id, event_id):
        return jsonify({"error": "already_registered"}), 400

    data = request.get_json(silent=True) or {}
    try:
        quantity = int(data.get("quantity", 1))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_quantity"}), 400
    if not 1 <= quantity <= MAX_TICKETS_PER_SIGNUP:
        return jsonify({"error": "invalid_quantity"}), 400

    price = _parse_price_rub(_event_price_for_tier(event, tier))
    if price <= 0:
        return jsonify({"error": "price_not_set"}), 400

    order_id = f"{event_id}-{telegram_id}-{int(time.time())}"
    sheets.create_pending_signup(telegram_id, event_id, order_id, quantity)

    notification_url = request.url_root.rstrip("/") + "/api/webhooks/prodamus"
    try:
        payment_url = prodamus_client.create_payment_link(
            order_id=order_id,
            title=event.get("Название", "") or "Участие в мероприятии",
            price=price,
            notification_url=notification_url,
            quantity=quantity,
            customer_phone=_normalize_phone(user.get("Телефон", "")),
            customer_extra=f"telegram_id={telegram_id}",
        )
    except RuntimeError as exc:
        return jsonify({"error": "payment_not_configured", "message": str(exc)}), 500

    return jsonify({"status": "ok", "payment_url": payment_url})


@api.route("/webhooks/prodamus", methods=["POST"])
def prodamus_webhook():
    """Подтверждение оплаты от Продамуса. Переход пользователя по urlSuccess
    подтверждением НЕ является — считаем оплаченным только по валидно
    подписанному вебхуку (см. prodamus_client.py)."""
    raw_body = request.get_data(as_text=True)
    signature = request.headers.get("Sign", "")
    payload = prodamus_client.parse_webhook_body(raw_body)

    if not prodamus_client.verify_webhook(payload, signature):
        return jsonify({"error": "invalid_signature"}), 400

    order_id = payload.get("order_num") or payload.get("order_id")
    if not order_id:
        return jsonify({"error": "missing_order_id"}), 400

    status = SIGNUP_STATUS_PAID if payload.get("payment_status") == "success" else SIGNUP_STATUS_FAILED
    sheets.set_signup_status(order_id, status)
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
        try:
            quantity = int(signup.get("Количество") or 1)
        except ValueError:
            quantity = 1
        item = {
            "id": event["id"],
            "title": event.get("Название", ""),
            "date": event.get("Дата", ""),
            "time": event.get("Время", ""),
            "place": event.get("Место", ""),
            "quantity": quantity,
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
