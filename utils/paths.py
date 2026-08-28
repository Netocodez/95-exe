from pathlib import Path
import os

APP_NAME = "2NDAND95"


def get_app_data_dir():
    """
    Returns a writable base directory depending on the environment.

    Windows Desktop (Nuitka):
        C:\\Users\\<User>\\AppData\\Local\\2NDAND95

    Linux/Render:
        <project_root>/data
    """

    if os.name == "nt":
        # Windows desktop
        base_dir = Path(os.getenv("LOCALAPPDATA")) / APP_NAME
    else:
        # Linux (Render, Ubuntu, etc.)
        base_dir = Path.cwd() / "data"

    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


APP_DATA = get_app_data_dir()

OUTPUTS = APP_DATA / "outputs"
UPLOADS = APP_DATA / "uploads"
TEMP = APP_DATA / "temp"
LOGS = APP_DATA / "logs"

for folder in (OUTPUTS, UPLOADS, TEMP, LOGS):
    folder.mkdir(parents=True, exist_ok=True)