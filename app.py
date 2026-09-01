import os

from flask import Flask, make_response, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from routes import api


def create_app():
    app = Flask(__name__)
    app.secret_key = Config.SECRET_KEY

    # За Railway (и вообще любым PaaS-прокси) приложение видит только
    # внутренний http-коннект от прокси, а не реальный https от браузера.
    # Без этого request.url_root/request.is_secure врут (http вместо https) —
    # это ломает и Secure-куки сессии, и URL вебхука для Продамуса, который
    # собирается из request.url_root в routes.py.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Мини-апп открывается внутри Telegram (часто как cross-site iframe/webview),
    # поэтому в проде куки сессии должны быть SameSite=None; Secure (требует HTTPS,
    # который даёт ngrok/Railway). В DEV_MODE тестируем через обычный http://localhost.
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax" if Config.DEV_MODE else "None"
    app.config["SESSION_COOKIE_SECURE"] = not Config.DEV_MODE

    app.register_blueprint(api)

    @app.after_request
    def fix_font_mimetype(response):
        # На части Windows-машин Werkzeug не знает .woff2 и отдаёт его как
        # application/octet-stream — chrome такое иногда блокирует. Правим явно.
        if request.path.endswith(".woff2"):
            response.headers["Content-Type"] = "font/woff2"
        return response

    @app.context_processor
    def inject_versioned_static():
        # Telegram WebView агрессивно кэширует статику по URL. Добавляем в ссылку
        # ?v=<время изменения файла>, чтобы после каждого деплоя браузер видел
        # новый URL и подтягивал свежие css/js, не дожидаясь ручной очистки кэша.
        def versioned_static(filename):
            path = os.path.join(app.static_folder, filename)
            try:
                version = int(os.path.getmtime(path))
            except OSError:
                version = 0
            return f"{url_for('static', filename=filename)}?v={version}"

        return {"versioned_static": versioned_static}

    @app.route("/")
    def index():
        # Сама HTML-страница не должна кэшироваться (в отличие от статики, у которой
        # версия зашита в URL) — иначе Telegram WebView может годами отдавать старую
        # разметку и никогда не узнать про новые ссылки на css/js.
        response = make_response(render_template("index.html", dev_mode=Config.DEV_MODE))
        response.headers["Cache-Control"] = "no-store, must-revalidate"
        return response

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEV_MODE, threaded=True)
