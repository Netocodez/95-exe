"""Prepare update.json after a GitHub Release ZIP has been uploaded."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from version import __version__


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip", type=Path)
    parser.add_argument("--download-url", required=True)
    parser.add_argument("--note", action="append", default=[])
    parser.add_argument("--mandatory", action="store_true")
    args = parser.parse_args()

    digest = sha256(args.zip)
    manifest = {
        "version": __version__,
        "release_date": date.today().isoformat(),
        "mandatory": args.mandatory,
        "download_url": args.download_url,
        "sha256": digest,
        "release_notes": args.note,
    }
    Path("update.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("update.json updated successfully.")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
