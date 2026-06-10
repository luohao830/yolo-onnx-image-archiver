from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


SUPPORTED_IMAGE_SUFFIXES = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".gif"}
)


def extract_upload_archive(archive_path: Path, out_dir: Path) -> list[Path]:
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    resolved_out_dir = out_dir.resolve()
    members: list[tuple[zipfile.ZipInfo, Path]] = []

    with zipfile.ZipFile(archive_path) as zf:
        for info in zf.infolist():
            target = _resolve_member_path(resolved_out_dir, info.filename)
            if info.is_dir():
                continue
            if target.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
                continue

            members.append((info, target))

    temp_out_dir = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}-", dir=out_dir.parent))
    extracted = [out_dir / target.relative_to(resolved_out_dir) for _, target in members]

    try:
        with zipfile.ZipFile(archive_path) as zf:
            for info, target in members:
                temp_target = temp_out_dir / target.relative_to(resolved_out_dir)
                temp_target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, temp_target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
        _replace_output_dir(temp_out_dir, out_dir)
    except Exception:
        shutil.rmtree(temp_out_dir, ignore_errors=True)
        raise

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


def _replace_output_dir(temp_out_dir: Path, out_dir: Path) -> None:
    if out_dir.exists():
        if not out_dir.is_dir():
            raise ValueError("输出目录必须是目录")
        if any(out_dir.iterdir()):
            raise ValueError("输出目录必须为空")
        out_dir.rmdir()
    temp_out_dir.replace(out_dir)
