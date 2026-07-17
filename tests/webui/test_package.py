"""webui/processing.py 的 package_output_dir 测试：验证产物为不压缩 zip（zip -r -0）。"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from webui.processing import package_output_dir


def test_package_uses_zip_stored(tmp_path: Path) -> None:
    out_dir = tmp_path / "run1"
    (out_dir / "person" / "images").mkdir(parents=True)
    (out_dir / "person" / "images" / "a.jpg").write_bytes(b"img-a")
    (out_dir / "no_detection" / "images").mkdir(parents=True)
    (out_dir / "no_detection" / "images" / "b.jpg").write_bytes(b"img-b")

    pkg = package_output_dir(out_dir)

    assert Path(pkg.zip_saved_path).exists()
    assert Path(pkg.zip_saved_path).stem.startswith("run1")
    with zipfile.ZipFile(pkg.zip_saved_path) as zf:
        for info in zf.infolist():
            assert info.compress_type == zipfile.ZIP_STORED, (
                f"{info.filename} 应为 ZIP_STORED（不压缩），实际 compress_type={info.compress_type}"
            )
        names = {i.filename for i in zf.infolist()}
        assert "person/images/a.jpg" in names
        assert "no_detection/images/b.jpg" in names


def test_package_progress_callback(tmp_path: Path) -> None:
    out_dir = tmp_path / "run2"
    (out_dir / "c").mkdir(parents=True)
    for i in range(3):
        (out_dir / "c" / f"{i}.jpg").write_bytes(b"x")

    seen = []
    pkg = package_output_dir(
        out_dir,
        progress_callback=lambda p: seen.append((p.processed, p.total)),
    )
    assert Path(pkg.zip_saved_path).exists()
    # 最后一次回调应为全部处理完成
    assert seen and seen[-1][0] == seen[-1][1] == 3


def test_package_progress_counts_only_images(tmp_path: Path) -> None:
    out_dir = tmp_path / "run-mixed"
    (out_dir / "person" / "images").mkdir(parents=True)
    (out_dir / "person" / "labels").mkdir(parents=True)
    (out_dir / "person" / "images" / "a.JPG").write_bytes(b"img-a")
    (out_dir / "person" / "images" / "b.png").write_bytes(b"img-b")
    (out_dir / "person" / "labels" / "a.txt").write_text("0 0.5 0.5 0.1 0.1", encoding="utf-8")

    seen = []
    pkg = package_output_dir(
        out_dir,
        progress_callback=lambda p: seen.append((p.processed, p.total)),
    )

    assert seen and seen[-1] == (2, 2)
    with zipfile.ZipFile(pkg.zip_saved_path) as zf:
        names = {info.filename for info in zf.infolist()}
    assert "person/images/a.JPG" in names
    assert "person/images/b.png" in names
    assert "person/labels/a.txt" in names


def test_package_progress_with_no_images(tmp_path: Path) -> None:
    out_dir = tmp_path / "run-text-only"
    out_dir.mkdir(parents=True)
    (out_dir / "labels.txt").write_text("label", encoding="utf-8")

    seen = []
    pkg = package_output_dir(
        out_dir,
        progress_callback=lambda p: seen.append((p.processed, p.total)),
    )

    assert Path(pkg.zip_saved_path).exists()
    assert seen and seen[0] == (0, 0) and seen[-1] == (0, 0)
    with zipfile.ZipFile(pkg.zip_saved_path) as zf:
        assert "labels.txt" in {info.filename for info in zf.infolist()}


def test_package_schedules_both_zip_files_for_cleanup(tmp_path: Path, monkeypatch) -> None:
    out_dir = tmp_path / "run-cleanup"
    out_dir.mkdir(parents=True)
    (out_dir / "a.jpg").write_bytes(b"img")

    scheduled = []

    def _capture(path: Path, delay_sec: int) -> None:
        scheduled.append((path, delay_sec))

    monkeypatch.setattr("webui.processing._schedule_delete", _capture)
    pkg = package_output_dir(out_dir)

    assert {path for path, _delay in scheduled} == {
        Path(pkg.zip_tmp_path),
        Path(pkg.zip_saved_path),
    }
    assert {delay for _path, delay in scheduled} == {600}


def test_repeated_package_uses_independent_saved_zip(tmp_path: Path) -> None:
    out_dir = tmp_path / "run-repeat"
    out_dir.mkdir(parents=True)
    (out_dir / "a.jpg").write_bytes(b"img")
    for existing in out_dir.parent.glob("run-repeat*.zip"):
        existing.unlink()

    first = package_output_dir(out_dir, keep_tmp_seconds=0)
    second = package_output_dir(out_dir, keep_tmp_seconds=0)

    assert Path(first.zip_saved_path).stem.startswith("run-repeat")
    assert Path(second.zip_saved_path).stem.startswith("run-repeat")
    assert first.zip_tmp_path != second.zip_tmp_path
    assert first.zip_saved_path != second.zip_saved_path
    assert Path(first.zip_saved_path).exists()
    assert Path(second.zip_saved_path).exists()
    with zipfile.ZipFile(first.zip_saved_path) as first_zip, zipfile.ZipFile(second.zip_saved_path) as second_zip:
        assert first_zip.namelist() == second_zip.namelist()


def test_package_missing_dir(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        package_output_dir(tmp_path / "does-not-exist")
