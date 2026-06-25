from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, BinaryIO

from backend.services.archive_ingest import SUPPORTED_IMAGE_SUFFIXES, extract_upload_archive
from backend.services.job_presenter import JobPresenter
from backend.services.runtime_paths import RuntimePaths

MAX_UPLOAD_FILE_BYTES = 100 * 1024 * 1024 * 1024


class UploadTooLargeError(ValueError):
    pass


class JobUploadStore:
    """上传大小限制、zip 解压、单图复制、输入图片计数。"""

    def __init__(self, runtime_paths: RuntimePaths) -> None:
        self._runtime_paths = runtime_paths

    def persist_public_upload(
        self,
        job_code: str,
        filename: str,
        file_obj: BinaryIO,
    ) -> tuple[Path, dict[str, Any]]:
        safe_filename = Path(filename or "upload").name or "upload"
        suffix = Path(safe_filename).suffix.lower()
        if suffix != ".zip" and suffix not in SUPPORTED_IMAGE_SUFFIXES:
            raise ValueError("仅支持图片文件或 zip 压缩包")

        upload_dir = self._runtime_paths.uploads / job_code
        input_dir = self._runtime_paths.jobs / job_code / "input"
        upload_dir.mkdir(parents=True, exist_ok=True)
        raw_path = upload_dir / safe_filename

        size_bytes = self._copy_upload_with_size_limit(file_obj, raw_path)

        if input_dir.exists():
            shutil.rmtree(input_dir)

        if suffix == ".zip":
            extracted = extract_upload_archive(raw_path, input_dir)
            if not extracted:
                raise ValueError("压缩包内未找到支持的图片")
            return (
                input_dir,
                self._build_upload_event(
                    total=len(extracted),
                    filename=safe_filename,
                    size_bytes=size_bytes,
                ),
            )

        self._copy_single_image_to_input(raw_path, input_dir)
        return (
            input_dir,
            self._build_upload_event(
                total=self._count_input_images(input_dir),
                filename=safe_filename,
                size_bytes=size_bytes,
            ),
        )

    @staticmethod
    def _copy_upload_with_size_limit(file_obj: BinaryIO, raw_path: Path) -> int:
        written = 0
        try:
            with raw_path.open("wb") as dst:
                while True:
                    chunk = file_obj.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > MAX_UPLOAD_FILE_BYTES:
                        raise UploadTooLargeError("上传文件大小不能超过 100G")
                    dst.write(chunk)
        except Exception:
            raw_path.unlink(missing_ok=True)
            raise
        return written

    @staticmethod
    def _copy_single_image_to_input(source: Path, input_dir: Path) -> None:
        input_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_input_dir = Path(tempfile.mkdtemp(prefix=f".{input_dir.name}-", dir=input_dir.parent))
        try:
            shutil.copy2(source, temp_input_dir / source.name)
            temp_input_dir.replace(input_dir)
        except Exception:
            shutil.rmtree(temp_input_dir, ignore_errors=True)
            raise

    @staticmethod
    def _count_input_images(input_dir: Path) -> int:
        return sum(
            1
            for path in input_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
        )

    @staticmethod
    def _build_upload_event(
        *,
        total: int,
        filename: str,
        size_bytes: int,
    ) -> dict[str, Any]:
        return {
            "event_type": "uploaded",
            "message": "文件已接收，任务已进入队列",
            "payload_json": {
                "stage": "upload",
                "progress": 100,
                "total": total,
                "filename": filename,
                "size_bytes": size_bytes,
            },
        }
