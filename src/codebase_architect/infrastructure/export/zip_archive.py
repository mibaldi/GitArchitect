"""Zip a documentation folder for download."""

from __future__ import annotations

import zipfile
from pathlib import Path


def zip_directory(src_dir: Path, dest_zip: Path) -> Path:
    """Create ``dest_zip`` containing every file under ``src_dir`` (recursively)."""
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(src_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(src_dir).as_posix())
    return dest_zip
