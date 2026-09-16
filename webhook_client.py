"""Отправка данных анкеты на внешний вебхук (vakas-tools) при регистрации.

Если WEBHOOK_URL не задан в .env, send_application() тихо ничего не делает —
приложение работает и без вебхука, это дополнительная синхронизация, а не
обязательная часть регистрации.
"""
import requests

from config import Config

_TIMEOUT = 15


def send_application(payload: dict) -> None:
    """POST JSON с данными анкеты на Config.WEBHOOK_URL.
    Поднимает requests.RequestException при сбое — вызывающий код сам решает,
    насколько это критично (обычно нет: заявка в клуб не должна падать
    из-за недоступности внешнего сервиса)."""
    if not Config.WEBHOOK_URL:
        return

    resp = requests.post(Config.WEBHOOK_URL, json=payload, timeout=_TIMEOUT)
    resp.raise_for_status()


def notify_anketa_done(sb_id) -> None:
    """GET-колбэк в salebot сразу после того, как человек заполнил анкету в
    мини-аппе — подставляет sb_id (их client_id, НЕ telegram_id — их API
    требует именно его) в "{client_id}" внутри Config.SALEBOT_ANKETA_DONE_URL.
    Ничего не отправляет, если sb_id пуст (человек прошёл анкету раньше, чем
    salebot успел прислать связку telegram_id<->client_id). Поднимает
    requests.RequestException при сбое — как и send_application(), вызывающий
    код должен ловить и не ронять регистрацию из-за недоступности salebot."""
    if not Config.SALEBOT_ANKETA_DONE_URL or not sb_id:
        return

    url = Config.SALEBOT_ANKETA_DONE_URL.replace("{client_id}", str(sb_id))
    resp = requests.get(url, timeout=_TIMEOUT)
    resp.raise_for_status()
