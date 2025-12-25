from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Generator, Iterable, List, Optional, Sequence, Tuple


IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".gif")


def sanitize_label(label: str, fallback: str = "unknown") -> str:
    """
    将字符串转换为可用作标签/目录名的安全字符串，避免出现路径分隔符等非法字符。
    """
    label = (label or "").strip()
    if not label:
        return fallback
    safe: List[str] = []
    for ch in label:
        if ch.isalnum() or ch in {"-", "_", "."}:
            safe.append(ch)
        else:
            safe.append("_")
    cleaned = "".join(safe).strip("._-")
    return cleaned or fallback


def iter_images(dataset_dir: Path, exts: Sequence[str] = IMAGE_EXTS) -> Generator[str, None, None]:
    lower_exts = {e.lower() for e in exts}
    for path in dataset_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in lower_exts:
            yield str(path)


def chunked(items: Iterable[str], batch_size: int) -> Generator[List[str], None, None]:
    batch: List[str] = []
    for item in items:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def link_or_copy_to_dir(src: Path, dest_dir: Path, prefer_hardlink: bool = True) -> Tuple[Path, str]:
    """
    将文件以硬链接优先的方式落到目标目录，若失败则回退到复制。

    返回 (最终路径, 模式)；模式为 "hardlink" 或 "copy"。
    """
    if not src.exists():
        raise FileNotFoundError(f"源文件不存在: {src}")
    dest_dir.mkdir(parents=True, exist_ok=True)

    stem = src.stem
    suffix = src.suffix
    candidate = dest_dir / f"{stem}{suffix}"
    index = 1
    while candidate.exists():
        candidate = dest_dir / f"{stem}_{index}{suffix}"
        index += 1

    if prefer_hardlink:
        try:
            os.link(str(src), str(candidate))
            return candidate, "hardlink"
        except OSError:
            pass

    shutil.copy2(str(src), str(candidate))
    return candidate, "copy"


def ensure_empty_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def resolve_path(path_str: str, base_dir: Optional[Path] = None) -> Path:
    path = Path(path_str)
    if base_dir is not None and not path.is_absolute():
        path = base_dir / path
    return path.expanduser().resolve()

