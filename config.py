import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    GOOGLE_SHEETS_ID = os.environ.get("GOOGLE_SHEETS_ID", "")
    # На Railway (и любом PaaS без постоянного диска) секретный JSON-ключ сервис-
    # аккаунта нельзя закоммитить файлом — кладём его целиком в одну переменную
    # окружения. Если задана — используется она; иначе (локальная разработка)
    # читаем как обычно из файла credentials.json.
    GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
    GOOGLE_CREDENTIALS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    DEV_MODE = os.environ.get("DEV_MODE", "false").lower() == "true"
    PORT = int(os.environ.get("PORT", "5000"))

    WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")

    # Секрет для входящего вебхука от сейлбота (?token=...). Если не задан,
    # эндпоинт принимает запросы без проверки — задайте его, когда ngrok-адрес
    # станет известен сейлботу, чтобы никто посторонний не мог писать в таблицу.
    INCOMING_WEBHOOK_SECRET = os.environ.get("INCOMING_WEBHOOK_SECRET", "")

    # Продамус (payform.ru) — реальная оплата участия в мероприятиях.
    PRODAMUS_URL = os.environ.get("PRODAMUS_URL", "https://biznesbanya.payform.ru/")
    PRODAMUS_SECRET = os.environ.get("PRODAMUS_SECRET", "")
    # Куда Продамус вернёт пользователя после оплаты/отмены — обычно чат с ботом,
    # чтобы человек мог заново открыть мини-апп через кнопку меню.
    PRODAMUS_RETURN_URL = os.environ.get("PRODAMUS_RETURN_URL", "https://t.me/banniy_orden_bot")
