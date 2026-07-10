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


def iter_subdirs(root: Path, max_depth: int = 1) -> List[str]:
    """列出 root 下的子目录（相对路径）。

    默认 max_depth=1：仅枚举 root 的直接子目录，避免全量递归扫描导致页面卡顿。
    """
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


def resolve_images_dir(
    path_text: str,
    images_dir: Path,
    host_images_dir: Optional[Path] = None,
) -> Optional[Path]:
    """把用户输入的图片目录解析为容器内实际目录，兼容三种输入：

    1. 相对 images_dir 的子路径（如 uploads/20250101）→ images_dir/rel；
    2. 容器内绝对路径（/data/images 或其子目录）→ 直接 resolve；
    3. 宿主机绝对路径（如 /home/xxx/images/smoke-set）→ 若配置了
       host_images_dir（该目录被挂载到容器内 images_dir），把宿主机前缀
       替换为容器内前缀后使用。

    返回 None 表示输入为空或无法解析的相对路径。
    """
    raw = (path_text or "").strip()
    if not raw:
        return None

    candidate = Path(raw)
    if candidate.is_absolute():
        resolved = candidate.expanduser().resolve()
        # 宿主机绝对路径换算：把已知宿主机挂载前缀替换为容器内 images_dir
        if host_images_dir is not None:
            host_prefix = Path(str(host_images_dir)).expanduser().resolve()
            try:
                rel_to_host = resolved.relative_to(host_prefix)
            except ValueError:
                rel_to_host = None
            if rel_to_host is not None:
                return (images_dir / rel_to_host).resolve()
        return resolved

    rel = ensure_relative(raw)
    if rel is None:
        return None
    return (images_dir / rel).resolve()

