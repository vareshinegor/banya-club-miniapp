"""Оплата участия в мероприятиях через Продамус (payform.ru).

Схема: бэкенд формирует подписанную платёжную ссылку и отдаёт её фронтенду,
пользователь оплачивает на стороне Продамуса, а подтверждением служит
только вебхук с валидной подписью на /api/webhooks/prodamus — переход
пользователя по urlSuccess подтверждением оплаты НЕ является (так по
документации Продамуса: ссылку на success можно открыть и без оплаты).

Алгоритм подписи — ровно тот, что описан в официальной документации
(https://help.prodamus.ru/payform/integracii/rest-api/instrukcii-dlya-samostoyatelnaya-integracii-servisov):
привести все значения к строкам, отсортировать по ключам (в т.ч. вглубь),
сериализовать в JSON, ЭКРАНИРОВАТЬ / (важно: PHP json_encode делает это по
умолчанию, а Python json.dumps — нет; пакет prodamuspy этот шаг пропускает,
из-за чего реальный Продамус отвечает "Ошибка подписи" на любые данные с
хотя бы одним "/" — а он есть почти везде, т.к. в ссылках всегда есть
"https://"; поймано и проверено на реальном магазине перед тем, как этот
файл получил рабочую версию) и подписать HMAC-SHA256 секретным ключом.

parse() (разбор form-urlencoded тела вебхука в PHP-style вложенный dict)
берём из пакета prodamuspy как есть — там экранирование ни при чём.
"""
import hashlib
import hmac
import json
from urllib.parse import quote

from prodamuspy import ProdamusPy

from config import Config

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = ProdamusPy(Config.PRODAMUS_SECRET)
    return _client


def _sign(data: dict) -> str:
    obj_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    obj_json = obj_json.replace("/", "\\/")
    return hmac.new(
        Config.PRODAMUS_SECRET.encode("utf-8"),
        msg=obj_json.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def _verify(data: dict, signature: str) -> bool:
    expected = _sign(data)
    return bool(signature) and hmac.compare_digest(expected, signature.lower())


def _flatten(data, prefix=""):
    """Разворачивает вложенный dict/list в пары (ключ, значение) в PHP-нотации
    (products[0][name]=...), как ожидает Продамус в GET/POST-запросе."""
    items = []
    for key, value in data.items():
        full_key = f"{prefix}[{key}]" if prefix else str(key)
        if isinstance(value, dict):
            items.extend(_flatten(value, full_key))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                idx_key = f"{full_key}[{i}]"
                if isinstance(item, dict):
                    items.extend(_flatten(item, idx_key))
                else:
                    items.append((idx_key, item))
        else:
            items.append((full_key, value))
    return items


def create_payment_link(*, order_id: str, title: str, price: float, notification_url: str,
                         quantity: int = 1, customer_phone: str = "", customer_extra: str = "") -> str:
    """Строит подписанную ссылку на оплату. price — число в рублях.

    notification_url передаётся явно (а не берётся из конфига), потому что это
    реальный публичный адрес текущего запроса (request.url_root + путь) — его
    нельзя захардкодить, ngrok-домен и вообще хост могут меняться. Совпадает с
    URL, который также должен быть прописан в Продамусе: Личный кабинет →
    Настройки → Интеграция → Настройка уведомлений (per-request урл официально
    поддерживается не для всех типов интеграций, поэтому дублируем настройку
    на обеих сторонах, чтобы точно работало)."""
    if not Config.PRODAMUS_SECRET:
        raise RuntimeError("PRODAMUS_SECRET не задан в .env")

    data = {
        "do": "pay",
        "order_id": order_id,
        "products": [
            {"name": title, "price": f"{price:.2f}", "quantity": str(quantity)},
        ],
        "urlReturn": Config.PRODAMUS_RETURN_URL,
        "urlSuccess": Config.PRODAMUS_RETURN_URL,
        "urlNotification": notification_url,
    }
    if customer_phone:
        data["customer_phone"] = customer_phone
    if customer_extra:
        data["customer_extra"] = customer_extra

    data["signature"] = _sign(data)

    query = "&".join(f"{quote(str(k))}={quote(str(v))}" for k, v in _flatten(data))
    base = Config.PRODAMUS_URL.rstrip("/") + "/"
    return f"{base}?{query}"


def parse_webhook_body(raw_body: str) -> dict:
    return _get_client().parse(raw_body)


def verify_webhook(payload: dict, signature: str) -> bool:
    if not Config.PRODAMUS_SECRET:
        return False
    return _verify(payload, signature)
