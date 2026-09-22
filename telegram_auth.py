import hashlib
import hmac
import json
from typing import Optional
from urllib.parse import parse_qsl


def validate_init_data(init_data: str, bot_token: str) -> Optional[dict]:
    """Validate Telegram WebApp initData and return the parsed user info.

    Algorithm per https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    Returns None if the data is missing, malformed, or the signature doesn't match.
    """
    if not init_data or not bot_token:
        return None

    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    user_raw = data.get("user")
    if not user_raw:
        return None

    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        return None

    telegram_id = user.get("id")
    if telegram_id is None:
        return None

    return {
        "telegram_id": telegram_id,
        "username": user.get("username"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
    }
