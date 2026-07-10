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
    2. 宿主机绝对路径（如 /host/images/smoke-set）→ 若配置了 host_images_dir
       （宿主机侧路径，被挂载到容器内 images_dir），把宿主机前缀替换为容器内前缀；
    3. 容器内绝对路径 → 限定在 images_dir 子树内。

    安全：相对路径先经 ensure_relative 拦截 `..`，再校验 resolve() 后仍在
    images_dir 子树内（防 symlink 逃逸）；绝对路径不在允许范围时返回 None，
    不回退到任意路径。
    """
    raw = (path_text or "").strip()
    if not raw:
        return None

    images_root = images_dir.resolve()

    candidate = Path(raw)
    if candidate.is_absolute():
        resolved = candidate.expanduser().resolve()
        if host_images_dir is not None:
            host_prefix = host_images_dir.expanduser().resolve()
            try:
                rel_to_host = resolved.relative_to(host_prefix)
            except ValueError:
                # 不在允许的宿主机挂载目录范围内，拒绝访问
                return None
            return (images_dir / rel_to_host).resolve()
        # 未配置 host_images_dir：仅允许 images_dir 子树内的容器绝对路径
        try:
            resolved.relative_to(images_root)
        except ValueError:
            return None
        return resolved

    rel = ensure_relative(raw)
    if rel is None:
        return None
    resolved = (images_dir / rel).resolve()
    try:
        resolved.relative_to(images_root)
    except ValueError:
        # resolve() 跟随符号链接后逃逸出 images_dir，拒绝
        return None
    return resolved


