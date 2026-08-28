from flask import Blueprint, render_template, jsonify, current_app, request

from updater.checker import check_for_updates, prepare_and_launch_update, UpdateError
from version import APP_NAME, __version__

bp = Blueprint('home', __name__)


@bp.route('/')
def home():
    return render_template("index.html")


@bp.route("/api/license-status", methods=["GET"])
def get_license_status():
    status = current_app.config.get("LICENSE_STATUS", {
        "is_trial": False,
        "days_remaining": None
    })
    return jsonify(status)


@bp.route("/api/app-info", methods=["GET"])
def get_app_info():
    return jsonify({
        "name": APP_NAME,
        "version": __version__,
        "desktop": current_app.config.get("DESKTOP_MODE", False),
    })


@bp.route("/api/update/check", methods=["GET"])
def update_check():
    if not current_app.config.get("DESKTOP_MODE", False):
        return jsonify({"update_available": False, "desktop": False})

    update_info = check_for_updates()
    if not update_info:
        return jsonify({
            "update_available": False,
            "current_version": __version__,
        })

    return jsonify({
        "update_available": True,
        "current_version": __version__,
        "version": update_info.get("version"),
        "release_date": update_info.get("release_date"),
        "mandatory": bool(update_info.get("mandatory", False)),
        "release_notes": update_info.get("release_notes", []),
        "download_url": update_info.get("download_url"),
        "sha256": update_info.get("sha256"),
    })


@bp.route("/api/update/install", methods=["POST"])
def update_install():
    if not current_app.config.get("DESKTOP_MODE", False):
        return jsonify({"message": "Automatic updates are available only in the Windows desktop application."}), 400

    try:
        update_info = check_for_updates()
        if not update_info:
            return jsonify({"message": "You are already using the latest version."})

        # Download and verify before closing the current application.
        prepare_and_launch_update(update_info)

        def shutdown_after_response():
            import os
            import time
            time.sleep(2.0)
            print("[UPDATE] Closing current application for update...")
            os._exit(0)

        import threading
        threading.Thread(
            target=shutdown_after_response,
            daemon=True,
            name="update-shutdown",
        ).start()

        return jsonify({
            "success": True,
            "message": f"Updating to version {update_info.get('version')}...",
        })
    except UpdateError as exc:
        print(f"[UPDATE] {exc}")
        return jsonify({"message": str(exc)}), 400
    except Exception as exc:
        print(f"[UPDATE] Install failed: {exc}")
        return jsonify({"message": f"Update failed: {exc}"}), 500
