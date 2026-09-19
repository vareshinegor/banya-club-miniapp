"""Отдельный тестовый сервер на порту 5051 с DEV_MODE=true (?dev_id=... вместо
Telegram initData), чтобы гонять UI-проверки в браузере, не трогая .env и не
мешая боевому процессу на порту 5000.

Запуск: .venv\\Scripts\\python.exe scripts\\run_devtest.py
"""
import os
import sys
from pathlib import Path

os.environ["DEV_MODE"] = "true"
os.environ["PORT"] = "5051"
# Тестовый сервер не должен ходить в боевые внешние интеграции (CRM, salebot):
# пустая переменная окружения отключает отправку и не перезаписывается .env.
os.environ["WEBHOOK_URL"] = ""
os.environ["SALEBOT_ANKETA_DONE_URL"] = ""

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app  # noqa: E402
from config import Config  # noqa: E402

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=False, threaded=True)
