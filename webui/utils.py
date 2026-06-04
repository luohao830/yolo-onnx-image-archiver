from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional


LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


_FILENAME_SAFE_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def sanitize_filename(name: str, fallback: str = "file") -> str:
    name = (name or "").strip()
    if not name:
        return fallback
    cleaned = _FILENAME_SAFE_RE.sub("_", name).strip("._-")
    return cleaned or fallback


def now_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def data_dir_from_env(env_key: str, default: str) -> Path:
    value = os.environ.get(env_key, default)
    return Path(value).expanduser().resolve()


def iter_subdirs(root: Path, max_depth: int = 2) -> List[str]:
    out: List[str] = []
    if not root.exists():
        return out
    root = root.resolve()

    def _walk(current: Path, rel: Path, depth: int) -> None:
        if depth > max_depth:
            return
        for child in sorted(current.iterdir()):
            if not child.is_dir():
                continue
            child_rel = rel / child.name
            out.append(str(child_rel))
            _walk(child, child_rel, depth + 1)

    _walk(root, Path("."), 1)
    out = [p for p in out if p != "."]
    return out


def list_models(models_dir: Path) -> List[str]:
    if not models_dir.exists():
        return []
    return sorted([p.name for p in models_dir.iterdir() if p.is_file() and p.suffix.lower() == ".onnx"])


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    i = 1
    while True:
        candidate = path.with_name(f"{stem}_{i}{suffix}")
        if not candidate.exists():
            return candidate
        i += 1


def ensure_relative(path_text: str) -> Optional[str]:
    raw = (path_text or "").strip().replace("\\", "/")
    if not raw:
        return None
    if raw.startswith("/"):
        return None
    if ".." in Path(raw).parts:
        return None
    return raw

