from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix


def create_app():
    app = Flask(__name__)

    # Suporte a reverse proxy com subpath (ex: /app2/).
    # Lê os headers X-Forwarded-For, X-Forwarded-Proto e X-Forwarded-Prefix
    # enviados pelo Nginx para que url_for() gere URLs corretas em produção.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_prefix=1)

    from .routes import bp
    app.register_blueprint(bp)

    return app
