from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from webui.utils import sanitize_filename


def sanitize_label(label: str, fallback: str = "unknown") -> str:
    return sanitize_filename(label, fallback=fallback)


def _label_from_id(cls_id: int, class_names: Optional[List[str]]) -> str:
    if class_names is not None and 0 <= cls_id < len(class_names):
        raw = class_names[cls_id]
        return sanitize_label(raw.strip()) if raw.strip() else str(cls_id)
    return str(cls_id)


def normalize_execution_device(device: str) -> str:
    requested = (device or "auto").strip().lower()
    if requested not in {"auto", "cpu"}:
        raise ValueError(f"不支持的推理设备: {device}")
    return requested


def format_seconds_human(seconds: Optional[float]) -> str:
    if seconds is None:
        return "-"
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    return f"{seconds:.2f} s"


def _safe_annotated_name(src: Path) -> str:
    suffix = src.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}:
        return src.name
    return f"{src.stem}.jpg"
