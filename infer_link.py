from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import errno
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

import cv2
import numpy as np


LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".gif")


def get_logger(name: str = __name__) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


logger = get_logger(__name__)
_HARDLINK_WARNED = False


def sanitize_label(label: str, fallback: str = "unknown") -> str:
    label = (label or "").strip()
    if not label:
        return fallback
    safe: List[str] = []
    for ch in label:
        if ch.isalnum() or ch in {"-", "_", "."}:
            safe.append(ch)
        else:
            safe.append("_")
    cleaned = "".join(safe).strip("._-")
    return cleaned or fallback


def iter_images(root: Path, recursive: bool = True) -> Iterator[Path]:
    lower_exts = {e.lower() for e in IMAGE_EXTS}
    it = root.rglob("*") if recursive else root.iterdir()
    for p in it:
        if p.is_file() and p.suffix.lower() in lower_exts:
            yield p


def chunked(items: Iterable[Path], batch_size: int) -> Iterator[List[Path]]:
    batch: List[Path] = []
    for item in items:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def _letterbox(
    img_bgr: np.ndarray,
    imgsz: Tuple[int, int],
    color: Tuple[int, int, int] = (114, 114, 114),
) -> np.ndarray:
    target_h, target_w = imgsz
    h, w = img_bgr.shape[:2]
    scale = min(target_h / h, target_w / w)
    nh, nw = int(round(h * scale)), int(round(w * scale))
    resized = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((target_h, target_w, 3), color, dtype=resized.dtype)
    pad_w = (target_w - nw) // 2
    pad_h = (target_h - nh) // 2
    canvas[pad_h : pad_h + nh, pad_w : pad_w + nw] = resized
    return canvas


def _nms_xyxy(boxes: np.ndarray, scores: np.ndarray, iou_thres: float) -> List[int]:
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


def _load_class_names_from_sidecar(model_path: Path) -> Optional[List[str]]:
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


def _load_class_names(model_path: Path, session) -> Optional[List[str]]:
    try:
        meta = session.get_modelmeta()
        custom = getattr(meta, "custom_metadata_map", None) or {}
        raw = custom.get("names")
        if raw:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and "names" in parsed and isinstance(parsed["names"], list):
                return [str(x) for x in parsed["names"]]
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
            if isinstance(parsed, dict):
                out = []
                for k in sorted(parsed, key=lambda x: int(x)):
                    out.append(str(parsed[k]))
                return out
    except Exception:  # noqa: BLE001
        pass

    return _load_class_names_from_sidecar(model_path)


def _label_from_id(cls_id: int, class_names: Optional[Sequence[str]]) -> str:
    if class_names and 0 <= cls_id < len(class_names):
        return str(class_names[cls_id])
    return str(cls_id)


def predict_top1_labels(
    session,
    input_name: str,
    image_paths: Sequence[Path],
    class_names: Optional[Sequence[str]],
    imgsz: Tuple[int, int],
    conf_thres: float,
    iou_thres: float,
) -> List[Tuple[Path, str, Optional[float]]]:
    batch_imgs: List[np.ndarray] = []
    for p in image_paths:
        img_bgr = cv2.imread(str(p))
        if img_bgr is None:
            img_bgr = np.zeros((imgsz[0], imgsz[1], 3), dtype=np.uint8)
        img = _letterbox(img_bgr, imgsz=imgsz)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))
        batch_imgs.append(img)

    inp = np.stack(batch_imgs, axis=0)
    outputs = session.run(None, {input_name: inp})
    if not outputs:
        raise ValueError("ONNX 推理无输出")

    out = outputs[0]
    if out.ndim == 2:
        out = np.expand_dims(out, axis=0)
    if out.ndim != 3 or out.shape[2] < 6:
        raise ValueError(f"不支持的输出形状: {out.shape}（期望 [B,N,5+num_cls]）")

    results: List[Tuple[Path, str, Optional[float]]] = []
    for bi, p in enumerate(image_paths):
        pred = out[bi]
        if pred.size == 0:
            results.append((p, "no_detection", None))
            continue

        obj = pred[:, 4]
        cls_probs = pred[:, 5:]
        cls_id = np.argmax(cls_probs, axis=1)
        cls_score = cls_probs[np.arange(cls_probs.shape[0]), cls_id]
        conf = obj * cls_score

        keep = conf >= float(conf_thres)
        if not np.any(keep):
            results.append((p, "no_detection", None))
            continue

        pred = pred[keep]
        conf_f = conf[keep]
        cls_id_f = cls_id[keep]

        xy = pred[:, 0:2]
        wh = pred[:, 2:4]
        xyxy = np.concatenate([xy - wh / 2, xy + wh / 2], axis=1)

        keep_idx = _nms_xyxy(xyxy, conf_f, float(iou_thres))
        conf_f = conf_f[keep_idx]
        cls_id_f = cls_id_f[keep_idx]

        best_i = int(np.argmax(conf_f))
        best_cls = int(cls_id_f[best_i])
        best_conf = float(conf_f[best_i])

        label = sanitize_label(_label_from_id(best_cls, class_names), fallback=str(best_cls))
        results.append((p, label, best_conf))

    return results


def hardlink_or_copy(src: Path, dest: Path, copy_fallback: bool = True) -> str:
    global _HARDLINK_WARNED  # noqa: PLW0603
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
        i = 1
        candidate = dest.parent / f"{stem}_{i}{suffix}"
        while candidate.exists():
            i += 1
            candidate = dest.parent / f"{stem}_{i}{suffix}"
        dest = candidate
    try:
        os.link(str(src), str(dest))
        return "hardlink"
    except OSError as exc:
        if not _HARDLINK_WARNED:
            _HARDLINK_WARNED = True
            if exc.errno == errno.EXDEV:
                logger.warning(
                    "硬链接失败：跨文件系统（images 与 out 不在同一挂载/文件系统），已回退复制；"
                    "请把 --out 指到 images 同一挂载下的目录（例如 /data/images/output）"
                )
            else:
                logger.warning("硬链接失败（errno=%s）：%s，已回退复制", exc.errno, exc)
        if not copy_fallback:
            raise
    shutil.copy2(str(src), str(dest))
    return "copy"


def main() -> int:
    parser = argparse.ArgumentParser(description="ONNXRuntime-GPU 推理并按类别硬链接归档（top1）")
    parser.add_argument("--model", required=True, help="ONNX 模型路径（.onnx）")
    parser.add_argument("--images", required=True, help="图片目录")
    parser.add_argument("--out", required=True, help="输出目录（输出/类别/xxx.jpg）")
    parser.add_argument("--imgsz", type=int, default=None, help="推理尺寸（默认自动取模型输入尺寸，否则 640）")
    parser.add_argument("--conf", type=float, default=0.25, help="置信度阈值")
    parser.add_argument("--iou", type=float, default=0.45, help="NMS IoU 阈值")
    parser.add_argument("--batch", type=int, default=16, help="batch size")
    parser.add_argument("--recursive", action="store_true", help="递归扫描子目录")
    parser.add_argument("--dry-run", action="store_true", help="只打印不落盘")
    parser.add_argument(
        "--no-copy-fallback",
        action="store_true",
        help="硬链接失败时不回退复制（默认会复制）",
    )
    args = parser.parse_args()

    model_path = Path(args.model).expanduser().resolve()
    if model_path.suffix.lower() != ".onnx":
        raise SystemExit("仅支持 .onnx 模型")
    if not model_path.exists():
        raise SystemExit(f"模型不存在: {model_path}")

    images_dir = Path(args.images).expanduser().resolve()
    if not images_dir.exists():
        raise SystemExit(f"图片目录不存在: {images_dir}")

    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    import onnxruntime as ort

    session = ort.InferenceSession(
        str(model_path),
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    providers = session.get_providers()
    if "CUDAExecutionProvider" not in providers:
        logger.warning("CUDAExecutionProvider 未启用（将使用 CPU 推理），当前 providers=%s", providers)
    inputs = session.get_inputs()
    if not inputs:
        raise SystemExit("ONNX 模型无输入")
    input_name = inputs[0].name
    input_shape = inputs[0].shape or []
    fixed_batch = input_shape[0] if len(input_shape) >= 1 and isinstance(input_shape[0], int) else None
    fixed_h = input_shape[2] if len(input_shape) >= 3 and isinstance(input_shape[2], int) else None
    fixed_w = input_shape[3] if len(input_shape) >= 4 and isinstance(input_shape[3], int) else None

    if fixed_batch == 1 and int(args.batch) != 1:
        logger.warning("模型输入 batch 固定为 1，将强制 batch=1（当前=%d）", int(args.batch))
        args.batch = 1

    if args.imgsz is None:
        if fixed_h and fixed_w:
            imgsz = (int(fixed_h), int(fixed_w))
        else:
            imgsz = (640, 640)
    else:
        imgsz = (int(args.imgsz), int(args.imgsz))
        if fixed_h and fixed_w and (imgsz[0] != int(fixed_h) or imgsz[1] != int(fixed_w)):
            logger.warning(
                "参数 imgsz=%s 与模型输入 HxW=%dx%d 不一致，将使用模型输入尺寸",
                imgsz,
                int(fixed_h),
                int(fixed_w),
            )
            imgsz = (int(fixed_h), int(fixed_w))

    class_names = _load_class_names(model_path, session)
    if class_names:
        logger.info("类别数: %d", len(class_names))
    else:
        logger.warning("未找到类别名，将使用 cls_id 作为类别名")

    total = 0
    moved = 0
    hardlinked = 0
    copied = 0
    exists = 0
    by_label: Dict[str, int] = {}

    paths = iter_images(images_dir, recursive=bool(args.recursive))
    for batch in chunked(paths, int(args.batch)):
        preds = predict_top1_labels(
            session=session,
            input_name=input_name,
            image_paths=batch,
            class_names=class_names,
            imgsz=imgsz,
            conf_thres=float(args.conf),
            iou_thres=float(args.iou),
        )
        for src, label, _conf in preds:
            total += 1
            safe_label = sanitize_label(label, fallback="no_detection")
            by_label[safe_label] = by_label.get(safe_label, 0) + 1

            dest = out_dir / safe_label / src.name
            if args.dry_run:
                continue
            mode = hardlink_or_copy(src, dest, copy_fallback=not bool(args.no_copy_fallback))
            moved += 1
            if mode == "hardlink":
                hardlinked += 1
            elif mode == "copy":
                copied += 1
            else:
                exists += 1

        if total % 200 == 0:
            logger.info("已处理 %d 张（hardlink=%d copy=%d exists=%d）", total, hardlinked, copied, exists)

    summary = "，".join([f"{k}:{v}" for k, v in sorted(by_label.items(), key=lambda x: (-x[1], x[0]))])
    logger.info(
        "完成：total=%d 落盘=%d hardlink=%d copy=%d exists=%d 统计=[%s]",
        total,
        moved,
        hardlinked,
        copied,
        exists,
        summary,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
