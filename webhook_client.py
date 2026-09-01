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
