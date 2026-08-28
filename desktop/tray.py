from __future__ import annotations

import os
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Callable, Optional

import pystray
from PIL import Image, ImageDraw
from pystray import MenuItem as item

from version import APP_NAME


class TrayApp:
    """System-tray controller for the local Flask application."""

    def __init__(
        self,
        url: str,
        shutdown_callback: Callable[[], None],
        check_update_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self.url = url
        self.shutdown_callback = shutdown_callback
        self.check_update_callback = check_update_callback
        self.icon: Optional[pystray.Icon] = None

    @staticmethod
    def _runtime_dir() -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent.parent

    def _load_icon(self) -> Image.Image:
        candidates = [
            self._runtime_dir() / "app.ico",
            self._runtime_dir() / "static" / "icon.ico",
            Path(__file__).resolve().parent.parent / "app.ico",
        ]
        for path in candidates:
            if path.exists():
                try:
                    return Image.open(path).convert("RGBA")
                except Exception:
                    pass

        image = Image.new("RGBA", (64, 64), (31, 78, 121, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((8, 8, 56, 56), radius=10, fill=(255, 255, 255, 255))
        draw.text((20, 23), "95", fill=(31, 78, 121, 255))
        return image

    def open_browser(self, _icon, _item) -> None:
        webbrowser.open(self.url)

    def check_updates(self, _icon, _item) -> None:
        if self.check_update_callback:
            threading.Thread(
                target=self.check_update_callback,
                daemon=True,
                name="update-check",
            ).start()

    def quit_app(self, icon, _item) -> None:
        try:
            icon.stop()
        finally:
            self.shutdown_callback()

    def run(self) -> None:
        menu = pystray.Menu(
            item("Open Analyzer", self.open_browser, default=True),
            item("Check for Updates", self.check_updates),
            pystray.Menu.SEPARATOR,
            item("Quit", self.quit_app),
        )

        self.icon = pystray.Icon(
            "analyzer_app",
            self._load_icon(),
            APP_NAME,
            menu,
        )
        self.icon.run()
