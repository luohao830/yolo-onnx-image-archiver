"""webui/utils.py 的 resolve_images_dir 测试：相对/绝对/宿主机路径换算。"""
from __future__ import annotations

from pathlib import Path

from webui.utils import resolve_images_dir


def test_empty_returns_none(tmp_path: Path) -> None:
    assert resolve_images_dir("", tmp_path) is None
    assert resolve_images_dir("   ", tmp_path) is None


def test_relative_joins_images_dir(tmp_path: Path) -> None:
    resolved = resolve_images_dir("uploads/20250101", tmp_path)
    assert resolved == (tmp_path / "uploads" / "20250101").resolve()


def test_relative_with_traversal_rejected(tmp_path: Path) -> None:
    assert resolve_images_dir("../escape", tmp_path) is None
    assert resolve_images_dir("a/../../b", tmp_path) is None


def test_container_absolute_used_directly(tmp_path: Path) -> None:
    abs_path = "/data/images/smoke-set"
    resolved = resolve_images_dir(abs_path, tmp_path)
    assert resolved == Path(abs_path).resolve()


def test_host_absolute_translated_to_container(tmp_path: Path) -> None:
    # 宿主机路径 /host/imgs 被 host_images_dir 指向，换算为容器内 images_dir
    host_root = tmp_path / "host"
    images_dir = tmp_path / "container"
    host_root.mkdir()
    images_dir.mkdir()
    resolved = resolve_images_dir(
        str(host_root / "smoke-set"),
        images_dir,
        host_images_dir=host_root,
    )
    assert resolved == (images_dir / "smoke-set").resolve()


def test_host_absolute_without_host_prefix_used_directly(tmp_path: Path) -> None:
    abs_path = "/some/other/path"
    resolved = resolve_images_dir(abs_path, tmp_path)
    assert resolved == Path(abs_path).resolve()