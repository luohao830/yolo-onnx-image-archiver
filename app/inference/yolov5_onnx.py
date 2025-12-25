from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np

from ..logging_utils import get_logger
from ..utils import sanitize_label


logger = get_logger(__name__)


@dataclass(frozen=True)
class Detection:
    cls_id: int
    label: str
    confidence: float
    xyxy: Tuple[float, float, float, float]


def _load_class_names(model_path: Path, ort_session) -> Optional[List[str]]:
    """
    优先从 ONNX metadata 读取 names；否则尝试读取同名 sidecar：
    - `xxx.names`（每行一个类别）
    - `xxx.json`（{"names": [...]} 或 直接是 list）
    """
    try:
        meta = ort_session.get_modelmeta()
        custom = getattr(meta, "custom_metadata_map", None) or {}
        names_raw = custom.get("names")
        if names_raw:
            try:
                parsed = json.loads(names_raw)
                if isinstance(parsed, dict) and "names" in parsed and isinstance(parsed["names"], list):
                    return [str(x) for x in parsed["names"]]
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
                if isinstance(parsed, dict):
                    # {0:"person",1:"car"} 形式
                    out = []
                    for k in sorted(parsed, key=lambda x: int(x)):
                        out.append(str(parsed[k]))
                    return out
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass

    names_file = model_path.with_suffix(".names")
    if names_file.exists():
        lines = [ln.strip() for ln in names_file.read_text(encoding="utf-8").splitlines()]
        names = [ln for ln in lines if ln]
        return names or None

    json_file = model_path.with_suffix(".json")
    if json_file.exists():
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("names"), list):
                return [str(x) for x in data["names"]]
            if isinstance(data, list):
                return [str(x) for x in data]
        except Exception:  # noqa: BLE001
            return None

    return None


def _letterbox(
    img: np.ndarray,
    new_shape: int = 640,
    color: Tuple[int, int, int] = (114, 114, 114),
) -> Tuple[np.ndarray, float, Tuple[int, int]]:
    """
    YOLOv5 常用 letterbox：保持比例缩放后 padding 到正方形。
    返回 (img, scale, (pad_w, pad_h))。
    """
    h, w = img.shape[:2]
    scale = min(new_shape / h, new_shape / w)
    nh, nw = int(round(h * scale)), int(round(w * scale))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((new_shape, new_shape, 3), color, dtype=resized.dtype)
    pad_w = (new_shape - nw) // 2
    pad_h = (new_shape - nh) // 2
    canvas[pad_h : pad_h + nh, pad_w : pad_w + nw] = resized
    return canvas, scale, (pad_w, pad_h)


def _nms_xyxy(
    boxes: np.ndarray,
    scores: np.ndarray,
    iou_thres: float,
) -> List[int]:
    """
    纯 numpy NMS，返回保留的 index。
    boxes: (N,4) xyxy
    """
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


class YoloV5Onnx:
    def __init__(self, model_path: Path, imgsz: int = 640):
        self.model_path = model_path
        self.imgsz = int(imgsz)

        import onnxruntime as ort  # 延迟导入，便于无依赖时静态检查

        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self.session = ort.InferenceSession(str(model_path), providers=providers)

        inputs = self.session.get_inputs()
        if not inputs:
            raise ValueError("ONNX 模型无输入")
        self.input_name = inputs[0].name

        self.class_names = _load_class_names(model_path, self.session)
        if self.class_names:
            logger.info("加载类别名：%s (%d)", model_path.name, len(self.class_names))
        else:
            logger.warning("未找到类别名，将使用 cls_id 作为 label：%s", model_path.name)

    def _label(self, cls_id: int) -> str:
        if self.class_names and 0 <= cls_id < len(self.class_names):
            return str(self.class_names[cls_id])
        return str(cls_id)

    def predict_top1(
        self,
        image_paths: Sequence[str],
        conf_thres: float = 0.25,
        iou_thres: float = 0.45,
    ) -> List[Tuple[str, str, Optional[float]]]:
        """
        返回 (image_path, safe_label, confidence)；无检测时 label=no_detection、confidence=None。
        """
        batch_imgs: List[np.ndarray] = []
        meta: List[Tuple[str, int, int, float, int, int]] = []
        # meta: (path, orig_w, orig_h, scale, pad_w, pad_h)
        for p in image_paths:
            img_bgr = cv2.imread(p)
            if img_bgr is None:
                batch_imgs.append(np.zeros((self.imgsz, self.imgsz, 3), dtype=np.uint8))
                meta.append((p, self.imgsz, self.imgsz, 1.0, 0, 0))
                continue
            orig_h, orig_w = img_bgr.shape[:2]
            img, scale, (pad_w, pad_h) = _letterbox(img_bgr, new_shape=self.imgsz)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = img.astype(np.float32) / 255.0
            img = np.transpose(img, (2, 0, 1))  # CHW
            batch_imgs.append(img)
            meta.append((p, orig_w, orig_h, scale, pad_w, pad_h))

        inp = np.stack(batch_imgs, axis=0)
        outputs = self.session.run(None, {self.input_name: inp})
        if not outputs:
            raise ValueError("ONNX 推理无输出")

        out = outputs[0]
        # 兼容 (B, N, 85) 或 (N, 85)
        if out.ndim == 2:
            out = np.expand_dims(out, axis=0)

        results: List[Tuple[str, str, Optional[float]]] = []
        for bi in range(out.shape[0]):
            pred = out[bi]
            if pred.size == 0:
                results.append((meta[bi][0], "no_detection", None))
                continue

            # pred: [x,y,w,h,obj,cls...]
            obj = pred[:, 4]
            cls_probs = pred[:, 5:]
            cls_id = np.argmax(cls_probs, axis=1)
            cls_score = cls_probs[np.arange(cls_probs.shape[0]), cls_id]
            conf = obj * cls_score

            keep = conf >= float(conf_thres)
            if not np.any(keep):
                results.append((meta[bi][0], "no_detection", None))
                continue

            pred = pred[keep]
            conf_f = conf[keep]
            cls_id_f = cls_id[keep]

            # xywh -> xyxy (on letterboxed image)
            xy = pred[:, 0:2]
            wh = pred[:, 2:4]
            xyxy = np.concatenate([xy - wh / 2, xy + wh / 2], axis=1)

            keep_idx = _nms_xyxy(xyxy, conf_f, float(iou_thres))
            xyxy = xyxy[keep_idx]
            conf_f = conf_f[keep_idx]
            cls_id_f = cls_id_f[keep_idx]

            best_i = int(np.argmax(conf_f))
            best_cls = int(cls_id_f[best_i])
            best_conf = float(conf_f[best_i])

            label = sanitize_label(self._label(best_cls), fallback=str(best_cls))
            results.append((meta[bi][0], label, best_conf))

        return results

