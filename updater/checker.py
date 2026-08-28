from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from version import APP_EXE_NAME, UPDATE_MANIFEST_URL, __version__


class UpdateError(RuntimeError):
    pass


def _version_tuple(version: str) -> tuple[int, ...]:
    try:
        parts = tuple(int(part) for part in version.strip().lstrip("v").split("."))
        return parts
    except (TypeError, ValueError):
        return (0,)


def is_newer_version(current: str, latest: str) -> bool:
    return _version_tuple(latest) > _version_tuple(current)


def check_for_updates() -> Optional[Dict[str, Any]]:
    """Return the GitHub update manifest when a newer release exists."""
    try:
        response = requests.get(
            UPDATE_MANIFEST_URL,
            timeout=8,
            headers={"Cache-Control": "no-cache"},
        )
        response.raise_for_status()
        data = response.json()
        latest = str(data.get("version", "")).strip()
        if latest and is_newer_version(__version__, latest):
            return data
    except Exception as exc:
        print(f"[UPDATE] Check failed: {exc}")
    return None


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _staging_dir() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        path = Path(local_app_data) / "2NDAND95" / "updates"
    else:
        path = Path(tempfile.gettempdir()) / "2NDAND95" / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_update(download_url: str, expected_sha256: str) -> Path:
    if not download_url or not expected_sha256:
        raise UpdateError("Update manifest is missing download_url or sha256.")

    destination = _staging_dir() / "update.zip"
    temporary = destination.with_suffix(".download")
    if temporary.exists():
        temporary.unlink()

    print(f"[UPDATE] Downloading: {download_url}")
    with requests.get(download_url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with temporary.open("wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output.write(chunk)

    actual = _sha256(temporary)
    if actual.lower() != expected_sha256.lower():
        temporary.unlink(missing_ok=True)
        raise UpdateError("SHA-256 validation failed for the downloaded update.")

    temporary.replace(destination)
    print(f"[UPDATE] Verified update: {destination}")
    return destination


def launch_updater(update_zip: Path) -> None:
    app_dir = _app_dir()
    updater_exe = app_dir / "updater.exe"
    if not updater_exe.exists():
        raise UpdateError(f"Updater executable not found: {updater_exe}")

    main_exe = Path(sys.executable).name if getattr(sys, "frozen", False) else APP_EXE_NAME
    command = [
        str(updater_exe),
        "--target-dir",
        str(app_dir),
        "--update-zip",
        str(update_zip),
        "--main-exe",
        main_exe,
        "--parent-pid",
        str(os.getpid()),
    ]
    print(f"[UPDATE] Launching updater: {command}")
    subprocess.Popen(command, cwd=str(app_dir), close_fds=True)


def prepare_and_launch_update(update_info: Dict[str, Any]) -> None:
    update_zip = download_update(
        str(update_info.get("download_url", "")),
        str(update_info.get("sha256", "")),
    )
    launch_updater(update_zip)
