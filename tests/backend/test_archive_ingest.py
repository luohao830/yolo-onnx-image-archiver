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


def test_extract_upload_archive_does_not_limit_image_count(tmp_path: Path) -> None:
    archive = tmp_path / "many-images.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for index in range(1001):
            zf.writestr(f"img-{index:04d}.jpg", b"x")

    extracted = extract_upload_archive(archive, tmp_path / "out")

    assert len(extracted) == 1001
    assert (tmp_path / "out" / "img-1000.jpg").read_bytes() == b"x"


def test_extract_upload_archive_does_not_limit_extracted_total_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(archive_ingest, "MAX_EXTRACTED_TOTAL_BYTES", 10, raising=False)
    archive = tmp_path / "large-uncompressed.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("a.jpg", b"12345")
        zf.writestr("b.jpg", b"678901")

    extracted = extract_upload_archive(archive, tmp_path / "out")

    assert [path.name for path in extracted] == ["a.jpg", "b.jpg"]
    assert (tmp_path / "out" / "b.jpg").read_bytes() == b"678901"


def test_extract_upload_archive_cleans_partial_files_on_copy_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = tmp_path / "broken.zip"
    out_dir = tmp_path / "out"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("first.jpg", b"first")
        zf.writestr("second.jpg", b"second")

    original_copyfileobj = archive_ingest.shutil.copyfileobj
    copy_calls = 0

    def flaky_copyfileobj(src, dst, length: int = 0) -> None:
        nonlocal copy_calls
        copy_calls += 1
        if copy_calls == 2:
            raise OSError("copy failed")
        original_copyfileobj(src, dst, length)

    monkeypatch.setattr(archive_ingest.shutil, "copyfileobj", flaky_copyfileobj)

    with pytest.raises(OSError, match="copy failed"):
        extract_upload_archive(archive, out_dir)

    assert not out_dir.exists() or not any(out_dir.rglob("*"))
