"""webui/infer_worker.py 的 detect_available_gpus 与任务级 GPU 分流逻辑测试。

通过 monkeypatch onnxruntime 的可用 providers 与 CUDA_VISIBLE_DEVICES 环境变量，
验证不同 GPU 可见性下的计数结果。
"""
from __future__ import annotations

import os

import pytest


def _set_providers(monkeypatch, providers):
    """注入一个伪造的 onnxruntime 模块，返回指定 providers。"""
    import sys
    import types

    fake = types.ModuleType("onnxruntime")

    def get_available_providers():
        return list(providers)

    fake.get_available_providers = get_available_providers
    monkeypatch.setitem(sys.modules, "onnxruntime", fake)


def test_no_cuda_provider_returns_zero(monkeypatch) -> None:
    _set_providers(monkeypatch, ["CPUExecutionProvider"])
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0,1")
    from webui.infer_worker import detect_available_gpus

    assert detect_available_gpus() == 0


def test_cuda_with_two_visible_devices(monkeypatch) -> None:
    _set_providers(monkeypatch, ["CUDAExecutionProvider", "CPUExecutionProvider"])
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0,1")
    from webui.infer_worker import detect_available_gpus

    assert detect_available_gpus() == 2


def test_cuda_default_one_when_not_limited(monkeypatch) -> None:
    _set_providers(monkeypatch, ["CUDAExecutionProvider"])
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    from webui.infer_worker import detect_available_gpus

    assert detect_available_gpus() == 1


def test_cuda_single_visible(monkeypatch) -> None:
    _set_providers(monkeypatch, ["CUDAExecutionProvider"])
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    from webui.infer_worker import detect_available_gpus

    assert detect_available_gpus() == 1