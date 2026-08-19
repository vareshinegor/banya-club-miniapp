from flask import Flask, render_template

from config import Config
from routes import api


def create_app():
    app = Flask(__name__)
    app.secret_key = Config.SECRET_KEY

    # Мини-апп открывается внутри Telegram (часто как cross-site iframe/webview),
    # поэтому в проде куки сессии должны быть SameSite=None; Secure (требует HTTPS,
    # который даёт ngrok). В DEV_MODE тестируем через обычный http://localhost.
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax" if Config.DEV_MODE else "None"
    app.config["SESSION_COOKIE_SECURE"] = not Config.DEV_MODE

    app.register_blueprint(api)

    @app.route("/")
    def index():
        return render_template("index.html", dev_mode=Config.DEV_MODE)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEV_MODE, threaded=True)
