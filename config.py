import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    GOOGLE_SHEETS_ID = os.environ.get("GOOGLE_SHEETS_ID", "")
    GOOGLE_CREDENTIALS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    DEV_MODE = os.environ.get("DEV_MODE", "false").lower() == "true"
    PORT = int(os.environ.get("PORT", "5000"))
