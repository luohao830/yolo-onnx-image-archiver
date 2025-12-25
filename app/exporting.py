from __future__ import annotations

import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Callable, Iterable, Optional, Tuple

from .logging_utils import get_logger
from .utils import ensure_dir, link_or_copy_to_dir, sanitize_label


logger = get_logger(__name__)


def export_zip_by_label(
    image_paths: Iterable[str],
    label: str,
    exports_dir: Path,
    zip_name: Optional[str] = None,
    prefer_hardlink: bool = True,
    progress: Optional[Callable[[float, str], None]] = None,
) -> Tuple[str, Path]:
    """
    生成 ZIP：内部结构为 `<label>/<filename>`。
    中间 staging 目录优先硬链接（失败回退复制），完成后自动清理。
    """
    ensure_dir(exports_dir)
    safe_label = sanitize_label(label, fallback="unknown")

    paths = list(image_paths)
    total = len(paths)
    if total == 0:
        raise ValueError(f"该标签下无图片可导出: {label}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    base = zip_name.strip() if zip_name else f"{safe_label}_{ts}"
    zip_path = exports_dir / f"{sanitize_label(base)}.zip"

    staging_root = Path(tempfile.mkdtemp(prefix="export_", dir=str(exports_dir)))
    try:
        label_dir = staging_root / safe_label
        label_dir.mkdir(parents=True, exist_ok=True)

        linked = 0
        copied = 0
        for idx, p in enumerate(paths, start=1):
            _, mode = link_or_copy_to_dir(
                src=Path(p),
                dest_dir=label_dir,
                prefer_hardlink=prefer_hardlink,
            )
            if mode == "hardlink":
                linked += 1
            else:
                copied += 1
            if progress is not None and idx % 20 == 0:
                progress(idx / max(total, 1), f"整理中：{idx}/{total}（hardlink={linked} copy={copied}）")

        if progress is not None:
            progress(0.95, "压缩中：写入 ZIP")

        files = [p for p in label_dir.iterdir() if p.is_file()]
        total_files = max(len(files), 1)
        with zipfile.ZipFile(
            zip_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as zf:
            for i, fp in enumerate(files, start=1):
                zf.write(fp, arcname=f"{safe_label}/{fp.name}")
                if progress is not None and i % 50 == 0:
                    progress(0.95 + 0.05 * (i / total_files), f"压缩中：{i}/{total_files}")

        if progress is not None:
            progress(1.0, "导出完成")

        msg = f"导出完成：label={label} count={total} zip={zip_path}（hardlink={linked} copy={copied}）"
        logger.info(msg)
        return msg, zip_path
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)

