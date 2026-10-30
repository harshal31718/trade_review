"""Code fingerprint used in the app's cache key, so a new deploy never serves a Review built by old code."""
from __future__ import annotations

import hashlib
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent


def code_version(engine_dir: Path = ENGINE_DIR) -> str:
    """Short hash of every .py file under ``engine_dir`` (paths and contents), stable across runs."""
    digest = hashlib.sha256()
    for path in sorted(engine_dir.rglob("*.py")):
        digest.update(path.relative_to(engine_dir).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]
