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


def test_package_missing_dir(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        package_output_dir(tmp_path / "does-not-exist")
