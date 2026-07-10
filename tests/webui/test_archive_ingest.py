"""webui/archive_ingest.py 的安全解压测试（纯 stdlib，无 ONNX 依赖）。"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from webui.archive_ingest import SUPPORTED_IMAGE_SUFFIXES, extract_upload_archive


def _make_zip(members: dict[str, bytes]) -> bytes:
    """members: {archive内相对路径: 内容字节}"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _write_zip(tmp_path: Path, name: str, raw: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(raw)
    return p


def test_extract_keeps_supported_images(tmp_path: Path) -> None:
    archive = _write_zip(
        tmp_path,
        "ok.zip",
        _make_zip(
            {
                "a.jpg": b"x",
                "sub/b.png": b"y",
                "ignore.txt": b"z",
                "ignore.json": b"{}",
            }
        ),
    )
    out_dir = tmp_path / "out"
    extracted = extract_upload_archive(archive, out_dir)

    names = sorted(p.name for p in extracted)
    assert names == ["a.jpg", "b.png"]
    assert (out_dir / "a.jpg").read_bytes() == b"x"
    assert (out_dir / "sub" / "b.png").read_bytes() == b"y"
    assert not (out_dir / "ignore.txt").exists()


def test_extract_supports_all_image_suffixes() -> None:
    assert ".webp" in SUPPORTED_IMAGE_SUFFIXES
    assert ".gif" in SUPPORTED_IMAGE_SUFFIXES
    assert ".txt" not in SUPPORTED_IMAGE_SUFFIXES


def test_extract_rejects_path_traversal(tmp_path: Path) -> None:
    archive = _write_zip(
        tmp_path,
        "evil.zip",
        _make_zip({"../escape.jpg": b"x"}),
    )
    out_dir = tmp_path / "out"
    with pytest.raises(ValueError):
        extract_upload_archive(archive, out_dir)


def test_extract_rejects_absolute_member(tmp_path: Path) -> None:
    archive = _write_zip(
        tmp_path,
        "abs.zip",
        _make_zip({"/etc/evil.jpg": b"x"}),
    )
    out_dir = tmp_path / "out"
    with pytest.raises(ValueError):
        extract_upload_archive(archive, out_dir)


def test_extract_rejects_non_empty_target(tmp_path: Path) -> None:
    archive = _write_zip(tmp_path, "ok.zip", _make_zip({"a.jpg": b"x"}))
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "preexisting.jpg").write_bytes(b"old")
    with pytest.raises(ValueError):
        extract_upload_archive(archive, out_dir)


def test_extract_empty_zip(tmp_path: Path) -> None:
    archive = _write_zip(tmp_path, "empty.zip", _make_zip({"readme.txt": b"hi"}))
    out_dir = tmp_path / "out"
    extracted = extract_upload_archive(archive, out_dir)
    assert extracted == []
    assert out_dir.exists() and not any(out_dir.iterdir())


def test_extract_rejects_oversized_file(tmp_path: Path) -> None:
    """单个文件超过 MAX_FILE_BYTES 时拒绝（zip 炸弹防护）。"""
    import webui.archive_ingest as ai

    archive = _write_zip(tmp_path, "big.zip", _make_zip({"big.jpg": b"0123456789abcdef"}))
    out_dir = tmp_path / "out"

    original_max = ai.MAX_FILE_BYTES
    ai.MAX_FILE_BYTES = 4
    try:
        with pytest.raises(ValueError):
            extract_upload_archive(archive, out_dir)
    finally:
        ai.MAX_FILE_BYTES = original_max


def test_extract_rejects_total_overflow(tmp_path: Path) -> None:
    """多文件累计超过 MAX_TOTAL_BYTES 时拒绝。"""
    import webui.archive_ingest as ai

    archive = _write_zip(
        tmp_path,
        "many.zip",
        _make_zip({"a.jpg": b"12345", "b.jpg": b"12345"}),
    )
    out_dir = tmp_path / "out"

    original_total = ai.MAX_TOTAL_BYTES
    ai.MAX_TOTAL_BYTES = 4
    try:
        with pytest.raises(ValueError):
            extract_upload_archive(archive, out_dir)
    finally:
        ai.MAX_TOTAL_BYTES = original_total
