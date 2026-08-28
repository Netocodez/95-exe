from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

EXCLUDED_RELATIVE_ROOTS = {
    "uploads",
    "outputs",
    "config",
    "data",
    "logs",
    "_temp_update",
    "_update_backup",
}
EXCLUDED_FILES = {"update.zip", "updater.exe"}


def _is_windows() -> bool:
    return os.name == "nt"


def _is_admin() -> bool:
    if not _is_windows():
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _elevate_if_needed() -> bool:
    """Re-run updater with UAC elevation when target directory is protected."""
    if not _is_windows() or _is_admin():
        return False

    print("[UPDATER] Requesting administrator elevation...")
    params = " ".join(f'"{arg}"' for arg in sys.argv[1:])
    
    # In Nuitka --onefile mode, sys.executable points to the temp directory.
    # sys.argv[0] gives the path to the actual launcher executable on disk.
    executable = os.path.abspath(sys.argv[0])

    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            executable,
            params,
            None,
            1,
        )
        if result <= 32:
            print(f"[UPDATER] UAC prompt declined or failed (code {result}). Continuing without elevation...")
            return False
        return True
    except Exception as err:
        print(f"[UPDATER] Elevation request failed: {err}. Proceeding without elevation...")
        return False


def _wait_for_parent(parent_pid: int) -> None:
    if parent_pid <= 0:
        time.sleep(1.5)
        return

    if not _is_windows():
        time.sleep(1.5)
        return

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x00100000, False, parent_pid)  # SYNCHRONIZE
    if handle:
        kernel32.WaitForSingleObject(handle, 15000)
        kernel32.CloseHandle(handle)
    else:
        time.sleep(1.5)
    time.sleep(0.5)


def _safe_extract(zip_path: Path, destination: Path) -> Path:
    """Extract while rejecting path traversal and unexpected absolute paths."""
    extract_root = destination / "_temp_update"
    if extract_root.exists():
        shutil.rmtree(extract_root, ignore_errors=True)
    extract_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise RuntimeError(f"Unsafe update archive path: {member.filename}")
            target = (extract_root / member_path).resolve()
            if extract_root.resolve() not in target.parents and target != extract_root.resolve():
                raise RuntimeError(f"Unsafe update archive path: {member.filename}")
        archive.extractall(extract_root)

    # Allow a ZIP containing a single top-level folder, but otherwise use the root.
    entries = [p for p in extract_root.iterdir()]
    if len(entries) == 1 and entries[0].is_dir():
        nested = entries[0]
        if (nested / "2nd-and-3rd-95-analysis.exe").exists():
            return nested
    return extract_root


def _should_skip(relative_path: Path) -> bool:
    if not relative_path.parts:
        return False
    if relative_path.parts[0] in EXCLUDED_RELATIVE_ROOTS:
        return True
    return relative_path.name in EXCLUDED_FILES


def _copy_tree(source_root: Path, target_root: Path, backup_root: Path, changed_files: list[Path]) -> None:
    for source in source_root.rglob("*"):
        relative = source.relative_to(source_root)
        if _should_skip(relative):
            continue
        target = target_root / relative
        backup = backup_root / relative

        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
        else:
            changed_files.append(target)
        shutil.copy2(source, target)


def _rollback(target_root: Path, backup_root: Path, new_files: list[Path]) -> None:
    for target in new_files:
        try:
            target.unlink(missing_ok=True)
        except Exception:
            pass
    if not backup_root.exists():
        return
    for backup in backup_root.rglob("*"):
        if backup.is_file():
            relative = backup.relative_to(backup_root)
            target = target_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)


def apply_update(target_dir: Path, update_zip: Path, main_exe: str, parent_pid: int) -> None:
    target_dir = target_dir.resolve()
    update_zip = update_zip.resolve()

    _wait_for_parent(parent_pid)

    staging_base = Path(tempfile.gettempdir()) / "2NDAND95-updater"
    staging_base.mkdir(parents=True, exist_ok=True)
    extract_root = None
    backup_root = staging_base / "backup"
    if backup_root.exists():
        shutil.rmtree(backup_root, ignore_errors=True)
    backup_root.mkdir(parents=True, exist_ok=True)

    new_files: list[Path] = []
    try:
        print(f"[UPDATER] Target: {target_dir}")
        extract_root = _safe_extract(update_zip, staging_base)
        _copy_tree(extract_root, target_dir, backup_root, new_files)
        print("[UPDATER] Update files installed successfully.")
    except Exception as exc:
        print(f"[UPDATER] Update failed: {exc}")
        try:
            _rollback(target_dir, backup_root, new_files)
            print("[UPDATER] Rollback completed.")
        except Exception as rollback_exc:
            print(f"[UPDATER] Rollback failed: {rollback_exc}")
        raise
    finally:
        if extract_root and extract_root.exists():
            shutil.rmtree(extract_root, ignore_errors=True)
        shutil.rmtree(backup_root, ignore_errors=True)
        update_zip.unlink(missing_ok=True)

    main_path = target_dir / main_exe
    if not main_path.exists():
        raise RuntimeError(f"Updated application executable not found: {main_path}")

    print(f"[UPDATER] Restarting: {main_path}")
    subprocess.Popen([str(main_path)], cwd=str(target_dir), close_fds=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="2nd & 3rd 95 Analyzer updater")
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--update-zip", required=True)
    parser.add_argument("--main-exe", required=True)
    parser.add_argument("--parent-pid", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if _elevate_if_needed():
        return 0

    try:
        apply_update(
            Path(args.target_dir),
            Path(args.update_zip),
            args.main_exe,
            args.parent_pid,
        )
        return 0
    except Exception as exc:
        print(f"[UPDATER] Fatal error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
