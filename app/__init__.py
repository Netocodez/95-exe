from flask import Flask
from pathlib import Path


def create_app():
    # Absolute path to the app package
    BASE_DIR = Path(__file__).resolve().parent

    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )

    # Writable user data is managed by utils.paths. Keep the Flask app
    # itself independent from the installation directory.

    from .routes import home, fetch

    app.config.setdefault("DESKTOP_MODE", False)

    app.register_blueprint(home.bp)
    app.register_blueprint(fetch.bp)

    return app