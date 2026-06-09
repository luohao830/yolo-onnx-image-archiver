from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

import backend.services.archive_ingest as archive_ingest
from backend.services.archive_ingest import extract_upload_archive


def test_extract_upload_archive_blocks_zip_slip(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.jpg", "boom")

    with pytest.raises(ValueError, match="非法压缩包路径"):
        extract_upload_archive(archive, tmp_path / "out")


def test_extract_upload_archive_only_returns_supported_images(tmp_path: Path) -> None:
    archive = tmp_path / "mixed.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("nested/keep.jpg", b"jpg-bytes")
        zf.writestr("cover.PNG", b"png-bytes")
        zf.writestr("notes.txt", "skip")

    extracted = extract_upload_archive(archive, tmp_path / "out")

    assert [path.relative_to(tmp_path / "out").as_posix() for path in extracted] == [
        "nested/keep.jpg",
        "cover.PNG",
    ]
    assert not (tmp_path / "out" / "notes.txt").exists()


def test_extract_upload_archive_blocks_too_many_images(tmp_path: Path) -> None:
    assert archive_ingest.MAX_EXTRACTED_IMAGE_COUNT == 1000

    archive = tmp_path / "too-many.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for index in range(1001):
            zf.writestr(f"img-{index:04d}.jpg", b"x")

    with pytest.raises(ValueError, match="压缩包图片数量超限"):
        extract_upload_archive(archive, tmp_path / "out")


def test_extract_upload_archive_blocks_total_size_limit(tmp_path: Path) -> None:
    assert archive_ingest.MAX_EXTRACTED_TOTAL_BYTES == 1024 * 1024 * 1024

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(archive_ingest, "MAX_EXTRACTED_TOTAL_BYTES", 10)

    archive = tmp_path / "too-large.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("a.jpg", b"12345")
        zf.writestr("b.jpg", b"678901")

    try:
        with pytest.raises(ValueError, match="压缩包解压总大小超限"):
            extract_upload_archive(archive, tmp_path / "out")
    finally:
        monkeypatch.undo()
