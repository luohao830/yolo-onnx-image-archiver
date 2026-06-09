from __future__ import annotations

import shutil
import zipfile
from pathlib import Path, PurePosixPath


SUPPORTED_IMAGE_SUFFIXES = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".gif"}
)
MAX_EXTRACTED_IMAGE_COUNT = 1000
MAX_EXTRACTED_TOTAL_BYTES = 1024 * 1024 * 1024


def extract_upload_archive(archive_path: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved_out_dir = out_dir.resolve()
    members: list[tuple[zipfile.ZipInfo, Path]] = []
    total_bytes = 0

    with zipfile.ZipFile(archive_path) as zf:
        for info in zf.infolist():
            target = _resolve_member_path(resolved_out_dir, info.filename)
            if info.is_dir():
                continue
            if target.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
                continue

            members.append((info, target))
            total_bytes += info.file_size

            if len(members) > MAX_EXTRACTED_IMAGE_COUNT:
                raise ValueError("压缩包图片数量超限")
            if total_bytes > MAX_EXTRACTED_TOTAL_BYTES:
                raise ValueError("压缩包解压总大小超限")

        extracted: list[Path] = []
        for info, target in members:
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted.append(target)

    return extracted


def _resolve_member_path(out_dir: Path, filename: str) -> Path:
    normalized = PurePosixPath(filename.replace("\\", "/"))
    if normalized.is_absolute() or ".." in normalized.parts:
        raise ValueError("非法压缩包路径")

    relative_parts = [part for part in normalized.parts if part not in ("", ".")]
    target = out_dir.joinpath(*relative_parts).resolve()

    try:
        target.relative_to(out_dir)
    except ValueError as exc:
        raise ValueError("非法压缩包路径") from exc

    return target
