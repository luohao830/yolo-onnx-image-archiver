"""对 webui/label_utils.py 和 webui/yolo_postprocess.py 纯函数的单元测试（无 ONNX 依赖）。"""
from pathlib import Path

import numpy as np
import pytest

from webui.label_utils import (
    _safe_annotated_name,
    format_seconds_human,
    normalize_execution_device,
    sanitize_label,
)
from webui.yolo_postprocess import (
    _normalize_yolo_output,
    _maybe_sigmoid,
    _nms_xyxy,
    _build_batch_detections,
)


# ── label_utils ────────────────────────────────────────────


def test_sanitize_label_passes_clean_text() -> None:
    assert sanitize_label("person") == "person"


def test_format_seconds_human() -> None:
    assert format_seconds_human(None) == "-"
    assert format_seconds_human(0.5) == "500 ms"
    assert format_seconds_human(1.5) == "1.50 s"


def test_normalize_execution_device() -> None:
    assert normalize_execution_device("cpu") == "cpu"
    assert normalize_execution_device("auto") == "auto"
    with pytest.raises(ValueError):
        normalize_execution_device("cuda")


def test_safe_annotated_name() -> None:
    assert _safe_annotated_name(Path("a.jpg")) == "a.jpg"
    assert _safe_annotated_name(Path("a.txt")) == "a.jpg"


# ── yolo_postprocess ───────────────────────────────────────


def test_normalize_yolo_output_keeps_bnc() -> None:
    x = np.zeros((1, 8400, 85), dtype=np.float32)
    y = _normalize_yolo_output(x)
    assert y.shape == (1, 8400, 85)


def test_normalize_yolo_output_transposes_bcn() -> None:
    """当第二维 < 6 且第一维 >= 6 时转置（老式 YOLO 输出）。"""
    # (1, 84, 4) — 第二维 < 6，第一维 >= 6 → 转置
    x = np.zeros((1, 84, 4), dtype=np.float32)
    y = _normalize_yolo_output(x)
    assert y.shape == (1, 4, 84)

    # (1, 84, 8400) — 两者都 >= 6，按 B,N,C 优先保留
    x2 = np.zeros((1, 84, 8400), dtype=np.float32)
    y2 = _normalize_yolo_output(x2)
    assert y2.shape == (1, 84, 8400)


def test_normalize_yolo_output_rejects_bad_shape() -> None:
    with pytest.raises(ValueError):
        _normalize_yolo_output(np.zeros((1, 2, 3), dtype=np.float32))


def test_maybe_sigmoid_passes_raw_in_range() -> None:
    x = np.array([0.1, 0.5, 0.9], dtype=np.float32)
    y = _maybe_sigmoid(x)
    np.testing.assert_array_almost_equal(y, x)


def test_maybe_sigmoid_applies_when_outside_01() -> None:
    x = np.array([-1.0, 0.0, 2.0], dtype=np.float32)
    y = _maybe_sigmoid(x)
    assert y.min() >= 0.0
    assert y.max() <= 1.0


def test_nms_keeps_non_overlapping() -> None:
    boxes = np.array([[0, 0, 10, 10], [20, 20, 30, 30]], dtype=np.float32)
    scores = np.array([0.9, 0.8], dtype=np.float32)
    keep = _nms_xyxy(boxes, scores, 0.5)
    assert keep == [0, 1]


def test_nms_suppresses_overlapping() -> None:
    boxes = np.array([[0, 0, 100, 100], [1, 1, 101, 101]], dtype=np.float32)
    scores = np.array([0.94, 0.93], dtype=np.float32)
    keep = _nms_xyxy(boxes, scores, 0.5)
    assert keep == [0]


def test_nms_empty() -> None:
    assert _nms_xyxy(np.empty((0, 4), dtype=np.float32), np.empty(0, dtype=np.float32), 0.5) == []


def test_build_batch_detections_single_image_no_detections() -> None:
    """conf 极高时无检测。"""
    batch = np.zeros((1, 8400, 85), dtype=np.float32)
    dets = _build_batch_detections(
        batch, [(480, 640)], (640, 640),
        class_names=["person"], conf=0.999, iou=0.5,
    )
    assert dets[0] == []


def test_build_batch_detections_filters_by_allowed_class_ids() -> None:
    """allowed_class_ids=[0] 应只保留 class 0 的检测。"""
    batch = np.zeros((1, 5, 6), dtype=np.float32)
    # 5 个检测：xyxy + cls0_conf + cls1_conf
    batch[:, :, :4] = [[10, 10, 50, 50]] * 5
    batch[:, 0, 4] = 0.95  # cls0 high conf
    batch[:, 0, 5] = 0.01
    batch[:, 1, 4] = 0.01
    batch[:, 1, 5] = 0.95  # cls1 high conf — 应被过滤
    batch[:, 2, 4] = 0.30
    batch[:, 2, 5] = 0.95  # cls1 high conf — 应被过滤
    batch[:, 3, 4] = 0.92  # cls0 high conf
    batch[:, 3, 5] = 0.03
    batch[:, 4, 4] = 0.10
    batch[:, 4, 5] = 0.95  # cls1 — 过滤

    dets = _build_batch_detections(
        batch, [(200, 200)], (200, 200),
        class_names=["person", "car"], conf=0.25, iou=0.5,
        allowed_class_ids={0},
    )
    # 只有 cls_id=0 且 conf>0.25 的保留：indices 0, 3
    labels = {d["label"] for d in dets[0]}
    assert "person" in labels or any(d["cls_id"] == 0 for d in dets[0])
    assert all(d["cls_id"] == 0 for d in dets[0])
