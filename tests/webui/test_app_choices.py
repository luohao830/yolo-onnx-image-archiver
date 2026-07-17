"""运行推理页快捷目录选择测试。"""
from __future__ import annotations

from pathlib import Path

import webui.app as app


def test_imageset_choices_includes_uploads_and_excludes_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "uploads" / "20260714_190218" / "1").mkdir(parents=True)
    (tmp_path / "dataset").mkdir()
    (tmp_path / "output").mkdir()
    (tmp_path / "not-a-directory.txt").write_text("ignore", encoding="utf-8")
    monkeypatch.setattr(app, "IMAGES_DIR", tmp_path)

    assert app._imageset_choices() == [
        str(tmp_path / "dataset"),
        str(tmp_path / "uploads"),
        str(tmp_path / "uploads" / "20260714_190218"),
        str(tmp_path / "uploads" / "20260714_190218" / "1"),
    ]


def test_model_path_is_restricted_to_models_dir(tmp_path: Path, monkeypatch) -> None:
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "safe.onnx").write_bytes(b"model")
    (models_dir / "not-model.txt").write_text("text", encoding="utf-8")
    outside = tmp_path / "outside.onnx"
    outside.write_bytes(b"outside")
    monkeypatch.setattr(app, "MODELS_DIR", models_dir)

    assert app._resolve_model_path("safe.onnx") == (models_dir / "safe.onnx").resolve()
    assert app._resolve_model_path(str(outside)) is None
    assert app._resolve_model_path("../outside.onnx") is None
    assert app._resolve_model_path("not-model.txt") is None
