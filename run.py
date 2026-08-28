import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path
from threading import Timer

from app import create_app
from desktop_sdk import LicenseManager
from version import APP_NAME, APP_EXE_NAME, __version__


# Single source of truth for the application version.
print(f"[APP] Starting {APP_NAME} v{__version__}")

# LicenseHub configuration remains compatible with the existing SDK integration.
license_manager = LicenseManager(
    server_url="https://licensehub-uejs.onrender.com",
    api_key="6c5bc98644a81d444621fad9a04370afa187eb7adbf8511c0eb8ecd782c741b7",
    app_name="95 Analyzer",
    app_version=__version__,
    org_id="Netocodes",
)

# Unified startup license check.
license_result = license_manager.startup_check(allow_trial=True)

if not license_result.is_valid:
    print(f"[LICENSE] Authentication failed: {license_result.message}")
    if not license_manager.start(allow_trial=False):
        sys.exit(1)

is_trial_mode = license_result.mode == "trial"
active_trial_info = license_result.data or {} if is_trial_mode else {}

app = create_app()

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 5000))
DESKTOP_MODE = HOST == "127.0.0.1"
app.config["DESKTOP_MODE"] = DESKTOP_MODE
app.config["APP_VERSION"] = __version__
app.config["APP_NAME"] = APP_NAME

# Attach License Metadata to Flask Config.
app.config["LICENSE_STATUS"] = {
    "is_trial": is_trial_mode,
    "days_remaining": active_trial_info.get("days_remaining", 0) if is_trial_mode else None,
    "expires_at": active_trial_info.get("expires_at") if is_trial_mode else None,
    "machine_id": license_manager.validator.machine_fingerprint,
    "license_mode": license_result.mode,
}


def runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def open_browser() -> None:
    webbrowser.open(f"http://{HOST}:{PORT}")


def is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def shutdown_application() -> None:
    print("[APP] Quit requested from system tray.")
    os._exit(0)


def check_updates_from_tray() -> None:
    """Open the UI; its update banner performs the actual check and action."""
    print("[UPDATE] Manual update check requested from tray.")
    open_browser()


def run_desktop() -> None:
    from desktop.tray import TrayApp

    if is_port_in_use(HOST, PORT):
        print(f"[APP] {HOST}:{PORT} is already in use. Opening existing analyzer.")
        open_browser()
        return

    Timer(1.5, open_browser).start()

    # Flask runs in a daemon thread; pystray owns the desktop process main thread.
    flask_thread = threading.Thread(
        target=lambda: app.run(
            host=HOST,
            port=PORT,
            debug=False,
            use_reloader=False,
        ),
        daemon=True,
        name="flask-server",
    )
    flask_thread.start()

    print(f"[APP] Desktop server starting at http://{HOST}:{PORT}")
    tray = TrayApp(
        url=f"http://{HOST}:{PORT}",
        shutdown_callback=shutdown_application,
        check_update_callback=check_updates_from_tray,
    )
    tray.run()


def run_server() -> None:
    print(f"[APP] Server starting at {HOST}:{PORT}")
    app.run(
        host=HOST,
        port=PORT,
        debug=False,
        use_reloader=False,
    )


if __name__ == "__main__":
    if DESKTOP_MODE:
        run_desktop()
    else:
        run_server()
