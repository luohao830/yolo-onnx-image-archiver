from __future__ import annotations

from typing import Any, List, Optional, Sequence, Tuple

import numpy as np


def _nms_xyxy(boxes: "np.ndarray", scores: "np.ndarray", iou_thres: float) -> List[int]:
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]

    keep: List[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        iou = inter / (areas[i] + areas[order[1:]] - inter)

        inds = np.where(iou <= iou_thres)[0]
        order = order[inds + 1]
    return keep


def _normalize_yolo_output(out: "np.ndarray") -> "np.ndarray":
    """
    Normalize common YOLO ONNX output layouts to [B, N, (5+num_cls)].

    Common cases:
    - [B, N, C] where C>=6
    - [B, C, N] (Ultralytics often exports YOLO11 as [B, 84, 8400])
    """
    if out.ndim != 3:
        raise ValueError(f"不支持的输出维度: {out.shape}")

    b, d1, d2 = out.shape
    if d2 >= 6:
        return out

    if d1 >= 6:
        return np.transpose(out, (0, 2, 1))

    raise ValueError(f"不支持的输出形状: {out.shape}（无法归一化为 [B,N,5+num_cls]）")


def _maybe_sigmoid(x: "np.ndarray") -> "np.ndarray":
    x = x.astype(np.float32, copy=False)
    try:
        vmax = float(np.nanmax(x))
        vmin = float(np.nanmin(x))
    except Exception:  # noqa: BLE001
        return x
    if vmax > 1.0 or vmin < 0.0:
        return 1.0 / (1.0 + np.exp(-x))
    return x


def _color_for_class(cls_id: int) -> Tuple[int, int, int]:
    import colorsys

    hue = (int(cls_id) * 0.61803398875) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.85, 0.95)
    return int(b * 255), int(g * 255), int(r * 255)  # BGR


def _draw_boxes(
    img_bgr: "np.ndarray",
    boxes_xyxy: "np.ndarray",
    cls_ids: "np.ndarray",
    scores: "np.ndarray",
    class_names: Optional[Sequence[str]],
) -> "np.ndarray":
    import cv2

    for (x1, y1, x2, y2), cls_id, score in zip(boxes_xyxy, cls_ids, scores):
        color = _color_for_class(int(cls_id))
        x1i, y1i, x2i, y2i = int(x1), int(y1), int(x2), int(y2)
        cv2.rectangle(img_bgr, (x1i, y1i), (x2i, y2i), color, 2)

        name = _get_label(int(cls_id), class_names)
        text = f"{name} {float(score):.2f}"
        (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        tx1 = max(0, x1i)
        ty1 = max(0, y1i - th - baseline - 4)
        cv2.rectangle(img_bgr, (tx1, ty1), (tx1 + tw + 6, ty1 + th + baseline + 6), color, -1)
        cv2.putText(
            img_bgr,
            text,
            (tx1 + 3, ty1 + th + 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            lineType=cv2.LINE_AA,
        )

    return img_bgr


def _get_label(cls_id: int, class_names: Optional[Sequence[str]]) -> str:
    from webui.label_utils import sanitize_label

    if class_names is not None and 0 <= cls_id < len(class_names):
        raw = class_names[cls_id]
        return sanitize_label(raw.strip()) if raw.strip() else str(cls_id)
    return str(cls_id)


def _build_batch_detections(
    batch_output: "np.ndarray",
    orig_hw_list: List[Tuple[int, int]],
    imgsz: Tuple[int, int],
    class_names: Optional[List[str]],
    conf: float,
    iou: float,
    allowed_class_ids: Optional[set] = None,
) -> List[List[dict[str, Any]]]:
    """将 batch 推理输出转为逐图检测结果列表。纯函数，无副作用。"""
    _ = _normalize_yolo_output(batch_output)
    batch_output = _maybe_sigmoid(batch_output)

    batch_dets: List[List[dict[str, Any]]] = [[] for _ in range(len(orig_hw_list))]

    for b_idx in range(batch_output.shape[0]):
        raw = batch_output[b_idx]
        cls_probs = raw[:, 5:]
        scores = np.max(cls_probs, axis=1)
        cls_ids = np.argmax(cls_probs, axis=1)

        if allowed_class_ids is not None:
            mask = np.isin(cls_ids, list(allowed_class_ids))
            scores = np.where(mask, scores, 0.0)

        conf_mask = scores > conf
        if not conf_mask.any():
            continue

        boxes_xyxy = raw[:, :4][conf_mask]
        filtered_scores = scores[conf_mask]
        filtered_cls = cls_ids[conf_mask]

        keep = _nms_xyxy(boxes_xyxy, filtered_scores, iou)
        boxes, scores_nms, cls_nms = (
            boxes_xyxy[keep],
            filtered_scores[keep],
            filtered_cls[keep],
        )

        # letterbox → 原始坐标
        boxes_orig = _xyxy_letterbox_to_original(
            boxes, orig_hw_list[b_idx], imgsz
        )

        img_dets: List[dict[str, Any]] = []
        for box, score, cls_id in zip(boxes_orig, scores_nms, cls_nms):
            x1, y1, x2, y2 = map(float, box.tolist())
            label = _get_label(int(cls_id), class_names)
            img_dets.append(
                {
                    "label": label,
                    "confidence": round(float(score), 4),
                    "bbox": [round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
                    "cls_id": int(cls_id),
                }
            )
        batch_dets[b_idx] = img_dets

    return batch_dets


def _xyxy_letterbox_to_original(
    boxes_xyxy: "np.ndarray",
    orig_hw: Tuple[int, int],
    imgsz: Tuple[int, int],
) -> "np.ndarray":
    orig_h, orig_w = orig_hw
    target_h, target_w = imgsz
    gain = min(float(target_h) / float(orig_h), float(target_w) / float(orig_w))
    scaled_w = float(orig_w) * gain
    scaled_h = float(orig_h) * gain
    pad_x = (float(target_w) - scaled_w) / 2.0
    pad_y = (float(target_h) - scaled_h) / 2.0

    boxes = boxes_xyxy.astype(np.float32, copy=True)
    boxes[:, [0, 2]] = (boxes[:, [0, 2]] - pad_x) / gain
    boxes[:, [1, 3]] = (boxes[:, [1, 3]] - pad_y) / gain
    boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0.0, float(orig_w))
    boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0.0, float(orig_h))
    return boxes


def _write_yolo_txt(
    txt_path: Path,
    boxes_xyxy: "np.ndarray",
    cls_ids: "np.ndarray",
    orig_hw: Tuple[int, int],
    imgsz: Tuple[int, int],
) -> None:
    from pathlib import Path as _Path

    if not isinstance(txt_path, _Path):
        txt_path = _Path(txt_path)
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    orig_h, orig_w = orig_hw
    if len(cls_ids) == 0:
        txt_path.write_text("", encoding="utf-8")
        return

    boxes = _xyxy_letterbox_to_original(boxes_xyxy, orig_hw=orig_hw, imgsz=imgsz)
    lines: List[str] = []
    for (x1, y1, x2, y2), cls_id in zip(boxes, cls_ids):
        x1f = float(np.clip(x1, 0.0, float(orig_w)))
        y1f = float(np.clip(y1, 0.0, float(orig_h)))
        x2f = float(np.clip(x2, 0.0, float(orig_w)))
        y2f = float(np.clip(y2, 0.0, float(orig_h)))
        bw = max(0.0, x2f - x1f)
        bh = max(0.0, y2f - y1f)
        xc = x1f + bw / 2.0
        yc = y1f + bh / 2.0
        if orig_w <= 0 or orig_h <= 0:
            continue
        lines.append(
            f"{int(cls_id)} {xc / float(orig_w):.6f} {yc / float(orig_h):.6f} "
            f"{bw / float(orig_w):.6f} {bh / float(orig_h):.6f}"
        )
    content = "\n".join(lines)
    if content:
        content += "\n"
    txt_path.write_text(content, encoding="utf-8")
