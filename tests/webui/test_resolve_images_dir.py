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


def test_container_absolute_within_images_dir(tmp_path: Path) -> None:
    # 容器内绝对路径必须在 images_dir 子树内（无 host_images_dir 时）
    resolved = resolve_images_dir(str(tmp_path / "smoke-set"), tmp_path)
    assert resolved == (tmp_path / "smoke-set").resolve()


def test_container_absolute_with_host_prefix_configured(tmp_path: Path) -> None:
    images_dir = tmp_path / "container"
    host_root = tmp_path / "host"
    images_dir.mkdir()
    host_root.mkdir()
    resolved = resolve_images_dir(
        str(images_dir / "uploads" / "20260714_101826"),
        images_dir,
        host_images_dir=host_root,
    )
    assert resolved == (images_dir / "uploads" / "20260714_101826").resolve()


def test_container_absolute_outside_images_dir_rejected(tmp_path: Path) -> None:
    # 容器内绝对路径不在 images_dir 子树内，拒绝（返回 None），避免路径遍历
    resolved = resolve_images_dir("/etc/passwd", tmp_path)
    assert resolved is None


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


def test_host_absolute_not_under_host_prefix_rejected(tmp_path: Path) -> None:
    # 配置了 host_images_dir 但输入绝对路径不在其前缀下，拒绝（不回退到任意路径）
    host_root = tmp_path / "host"
    images_dir = tmp_path / "container"
    host_root.mkdir()
    images_dir.mkdir()
    resolved = resolve_images_dir("/some/other/path", images_dir, host_images_dir=host_root)
    assert resolved is None


def test_relative_symlink_escape_rejected(tmp_path: Path) -> None:
    # images_dir 下存在指向外部的符号链接，resolve 后逃逸出子树，应拒绝
    images_dir = tmp_path / "imgs"
    images_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = images_dir / "escape"
    link.symlink_to(outside)
    assert resolve_images_dir("escape", images_dir) is None
