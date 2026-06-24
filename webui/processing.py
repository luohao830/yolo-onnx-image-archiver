from __future__ import annotations

import errno
import json
import os
import shutil
import tempfile
import threading
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

from webui.utils import get_logger, sanitize_filename, unique_path


logger = get_logger(__name__)
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".gif")
_CV2_RUNTIME_CONFIGURED = False


@dataclass(frozen=True)
class InferenceSummary:
    total: int
    written: int
    hardlinked: int
    copied: int
    failed: int
    txt_written: int
    elapsed_sec: float
    preprocess_sec: float
    inference_sec: float
    postprocess_sec: float
    hardlink_sec: float
    drawn: int
    draw_sec: float
    providers: List[str]
    cuda_enabled: bool
    requested_device: str
    used_batch: int
    used_imgsz: Tuple[int, int]
    input_shape: List
    output_shape: Optional[List]
    by_label: Dict[str, int]
    out_dir: str


@dataclass(frozen=True)
class PackageSummary:
    out_dir: str
    zip_tmp_path: str
    zip_saved_path: str


@dataclass(frozen=True)
class InferenceProgress:
    stage: str
    processed: int
    total: int
    remaining: int
    batch_size: int
    elapsed_sec: float
    avg_pre_batch_sec: Optional[float]
    avg_infer_batch_sec: Optional[float]
    avg_post_batch_sec: Optional[float]
    avg_write_batch_sec: Optional[float]
    eta_sec: Optional[float]


@dataclass(frozen=True)
class BatchWorkSummary:
    total: int
    written: int
    hardlinked: int
    copied: int
    failed: int
    txt_written: int
    drawn: int
    by_label: Dict[str, int]
    post_batch_sec: float
    write_batch_sec: float
    draw_batch_sec: float


def sanitize_label(label: str, fallback: str = "unknown") -> str:
    return sanitize_filename(label, fallback=fallback)


def iter_images(root: Path, recursive: bool) -> Iterator[Path]:
    lower_exts = {e.lower() for e in IMAGE_EXTS}

    def _walk(current: Path) -> Iterator[Path]:
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_file(follow_symlinks=False):
                            suffix = Path(entry.name).suffix.lower()
                            if suffix in lower_exts:
                                yield Path(entry.path)
                        elif recursive and entry.is_dir(follow_symlinks=False):
                            yield from _walk(Path(entry.path))
                    except OSError:
                        continue
        except OSError:
            return

    yield from _walk(root)


def count_images(
    root: Path,
    recursive: bool,
    *,
    report_every: int = 2000,
    progress_callback: Optional[Callable[[InferenceProgress], None]] = None,
) -> int:
    start_t = time.perf_counter()
    total = 0
    for total, _ in enumerate(iter_images(root, recursive=recursive), start=1):
        if progress_callback and (total == 1 or total % max(1, int(report_every)) == 0):
            progress_callback(
                InferenceProgress(
                    stage="counting",
                    processed=total,
                    total=0,
                    remaining=0,
                    batch_size=0,
                    elapsed_sec=max(0.0, float(time.perf_counter() - start_t)),
                    avg_pre_batch_sec=None,
                    avg_infer_batch_sec=None,
                    avg_post_batch_sec=None,
                    avg_write_batch_sec=None,
                    eta_sec=None,
                )
            )

    if progress_callback:
        progress_callback(
            InferenceProgress(
                stage="counting",
                processed=total,
                total=total,
                remaining=0,
                batch_size=0,
                elapsed_sec=max(0.0, float(time.perf_counter() - start_t)),
                avg_pre_batch_sec=None,
                avg_infer_batch_sec=None,
                avg_post_batch_sec=None,
                avg_write_batch_sec=None,
                eta_sec=None,
            )
        )
    return total


def collect_image_paths(
    root: Path,
    recursive: bool,
    *,
    report_every: int = 2000,
    progress_callback: Optional[Callable[[InferenceProgress], None]] = None,
) -> List[Path]:
    start_t = time.perf_counter()
    paths: List[Path] = []
    for idx, path in enumerate(iter_images(root, recursive=recursive), start=1):
        paths.append(path)
        if progress_callback and (idx == 1 or idx % max(1, int(report_every)) == 0):
            progress_callback(
                InferenceProgress(
                    stage="counting",
                    processed=idx,
                    total=0,
                    remaining=0,
                    batch_size=0,
                    elapsed_sec=max(0.0, float(time.perf_counter() - start_t)),
                    avg_pre_batch_sec=None,
                    avg_infer_batch_sec=None,
                    avg_post_batch_sec=None,
                    avg_write_batch_sec=None,
                    eta_sec=None,
                )
            )

    if progress_callback:
        progress_callback(
            InferenceProgress(
                stage="counting",
                processed=len(paths),
                total=len(paths),
                remaining=0,
                batch_size=0,
                elapsed_sec=max(0.0, float(time.perf_counter() - start_t)),
                avg_pre_batch_sec=None,
                avg_infer_batch_sec=None,
                avg_post_batch_sec=None,
                avg_write_batch_sec=None,
                eta_sec=None,
            )
        )
    return paths


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
    img_bgr,
    imgsz: Tuple[int, int],
    color: Tuple[int, int, int] = (114, 114, 114),
) -> "object":
    import cv2
    import numpy as np

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


def _nms_xyxy(boxes, scores, iou_thres: float) -> List[int]:
    import numpy as np

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


def _normalize_yolo_output(out) -> "object":
    """
    Normalize common YOLO ONNX output layouts to [B, N, (5+num_cls)].

    Common cases:
    - [B, N, C] where C>=6
    - [B, C, N] (Ultralytics often exports YOLO11 as [B, 84, 8400])
    """
    import numpy as np

    if out.ndim != 3:
        raise ValueError(f"不支持的输出维度: {out.shape}")

    b, d1, d2 = out.shape
    if d2 >= 6:
        # already [B, N, C]
        return out

    # try [B, C, N] -> [B, N, C]
    if d1 >= 6:
        return np.transpose(out, (0, 2, 1))

    raise ValueError(f"不支持的输出形状: {out.shape}（无法归一化为 [B,N,5+num_cls]）")


def _maybe_sigmoid(x):
    import numpy as np

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
    img_bgr,
    boxes_xyxy,
    cls_ids,
    scores,
    class_names: Optional[Sequence[str]],
) -> "object":
    import cv2

    for (x1, y1, x2, y2), cls_id, score in zip(boxes_xyxy, cls_ids, scores):
        color = _color_for_class(int(cls_id))
        x1i, y1i, x2i, y2i = int(x1), int(y1), int(x2), int(y2)
        cv2.rectangle(img_bgr, (x1i, y1i), (x2i, y2i), color, 2)

        name = _label_from_id(int(cls_id), class_names)
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


def _safe_annotated_name(src: Path) -> str:
    suffix = src.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}:
        return src.name
    return f"{src.stem}.jpg"


def _xyxy_letterbox_to_original(boxes_xyxy, orig_hw: Tuple[int, int], imgsz: Tuple[int, int]) -> "object":
    import numpy as np

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


def _write_yolo_txt(txt_path: Path, boxes_xyxy, cls_ids, orig_hw: Tuple[int, int], imgsz: Tuple[int, int]) -> None:
    import numpy as np

    txt_path.parent.mkdir(parents=True, exist_ok=True)
    orig_h, orig_w = orig_hw
    if len(cls_ids) == 0:
        txt_path.write_text("", encoding="utf-8")
        return

    boxes = _xyxy_letterbox_to_original(boxes_xyxy, orig_hw=orig_hw, imgsz=imgsz)
    lines: List[str] = []
    for (x1, y1, x2, y2), cls_id in zip(boxes, cls_ids):
        x1 = float(np.clip(x1, 0.0, float(orig_w)))
        y1 = float(np.clip(y1, 0.0, float(orig_h)))
        x2 = float(np.clip(x2, 0.0, float(orig_w)))
        y2 = float(np.clip(y2, 0.0, float(orig_h)))
        bw = max(0.0, x2 - x1)
        bh = max(0.0, y2 - y1)
        xc = x1 + bw / 2.0
        yc = y1 + bh / 2.0
        if orig_w <= 0 or orig_h <= 0:
            continue
        lines.append(
            f"{int(cls_id)} {xc / float(orig_w):.6f} {yc / float(orig_h):.6f} {bw / float(orig_w):.6f} {bh / float(orig_h):.6f}"
        )
    content = "\n".join(lines)
    if content:
        content += "\n"
    txt_path.write_text(content, encoding="utf-8")


def _category_images_dir(out_dir: Path, label: str, rel_parent: Path) -> Path:
    dest_dir = out_dir / label / "images"
    if rel_parent != Path("."):
        dest_dir = dest_dir / rel_parent
    return dest_dir


def _category_labels_dir(out_dir: Path, label: str, rel_parent: Path) -> Path:
    dest_dir = out_dir / label / "labels"
    if rel_parent != Path("."):
        dest_dir = dest_dir / rel_parent
    return dest_dir


def _ensure_label_tree(out_dir: Path, label: str, created_dirs: Set[Path]) -> None:
    base_dir = out_dir / label
    images_dir = base_dir / "images"
    labels_dir = base_dir / "labels"
    for path in (base_dir, images_dir, labels_dir):
        if path not in created_dirs:
            path.mkdir(parents=True, exist_ok=True)
            created_dirs.add(path)


def _load_class_names_from_sidecar(model_path: Path) -> Optional[List[str]]:
    for ext in (".names", ".txt"):
        names_file = model_path.with_suffix(ext)
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


def normalize_execution_device(device: str) -> str:
    requested = (device or "auto").strip().lower()
    if requested not in {"auto", "cpu"}:
        raise ValueError(f"不支持的推理设备: {device}")
    return requested


def format_seconds_human(seconds: Optional[float]) -> str:
    if seconds is None:
        return "计算中"
    total = max(0, int(round(float(seconds))))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes > 0:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def configure_cv2_runtime(cv2_module) -> None:
    global _CV2_RUNTIME_CONFIGURED  # noqa: PLW0603
    if _CV2_RUNTIME_CONFIGURED:
        return
    try:
        cv2_module.setUseOptimized(True)
    except Exception:  # noqa: BLE001
        pass
    try:
        cv2_module.setNumThreads(1)
    except Exception:  # noqa: BLE001
        pass
    _CV2_RUNTIME_CONFIGURED = True


def resolve_ort_input_config(input_type: str):
    import numpy as np

    ort_type = (input_type or "").strip().lower()
    if ort_type in {"tensor(float16)", "tensor(mlfloat16)"}:
        return np.float16, np.float16(1.0 / 255.0), True
    if ort_type in {"tensor(float)", "tensor(float32)"}:
        return np.float32, np.float32(1.0 / 255.0), True
    if ort_type == "tensor(uint8)":
        return np.uint8, None, False

    logger.warning("未识别的模型输入类型: %s，将按 float32 预处理", input_type)
    return np.float32, np.float32(1.0 / 255.0), True


def build_ort_providers(device: str = "auto") -> List[object]:
    requested = normalize_execution_device(device)
    if requested == "cpu":
        return ["CPUExecutionProvider"]

    return [
        (
            "CUDAExecutionProvider",
            {
                "cudnn_conv_algo_search": "HEURISTIC",
                "do_copy_in_default_stream": "1",
            },
        ),
        "CPUExecutionProvider",
    ]


def _label_from_id(cls_id: int, class_names: Optional[Sequence[str]]) -> str:
    if class_names and 0 <= cls_id < len(class_names):
        return str(class_names[cls_id])
    return str(cls_id)


def _infer_top1_for_batch(
    session,
    input_name: str,
    image_paths: Sequence[Path],
    class_names: Optional[Sequence[str]],
    imgsz: Tuple[int, int],
    conf_thres: float,
    iou_thres: float,
) -> List[Tuple[Path, str, Optional[float]]]:
    import cv2
    import numpy as np

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
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest = unique_path(dest)
    try:
        os.link(str(src), str(dest))
        return "hardlink"
    except OSError as exc:
        if exc.errno == errno.EXDEV:
            logger.warning("硬链接失败：跨文件系统，已回退复制（src=%s dest=%s）", src, dest)
        else:
            logger.warning("硬链接失败（errno=%s）：%s，已回退复制", exc.errno, exc)
        if not copy_fallback:
            raise
    shutil.copy2(str(src), str(dest))
    return "copy"


def _schedule_delete(path: Path, delay_sec: int = 300) -> None:
    def _worker() -> None:
        time.sleep(int(delay_sec))
        try:
            path.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            return

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def package_output_dir(out_dir: Path, *, keep_tmp_seconds: int = 300) -> PackageSummary:
    out_dir = out_dir.expanduser().resolve()
    if not out_dir.exists() or not out_dir.is_dir():
        raise ValueError(f"输出目录不存在: {out_dir}")

    tmp_dir = Path(tempfile.gettempdir()).resolve()
    zip_base = unique_path(tmp_dir / out_dir.name)
    zip_tmp = Path(shutil.make_archive(str(zip_base), "zip", root_dir=str(out_dir))).resolve()

    saved_base = unique_path(out_dir.parent / out_dir.name)
    zip_saved = saved_base.with_suffix(".zip")
    try:
        if zip_saved.resolve() != zip_tmp.resolve():
            shutil.copy2(str(zip_tmp), str(zip_saved))
        else:
            zip_saved = zip_tmp
    except FileNotFoundError:
        zip_saved = zip_tmp

    if keep_tmp_seconds > 0:
        _schedule_delete(zip_tmp, delay_sec=int(keep_tmp_seconds))

    return PackageSummary(out_dir=str(out_dir), zip_tmp_path=str(zip_tmp), zip_saved_path=str(zip_saved))


def run_inference(
    model_path: Path,
    images_dir: Path,
    out_dir: Path,
    *,
    recursive: bool,
    batch: int,
    imgsz: Optional[int],
    conf: float,
    iou: float,
    copy_fallback: bool,
    preprocess_workers: int = 4,
    prefetch_batches: int = 2,
    allowed_class_ids: Optional[Set[int]] = None,
    unmatched_label: str = "no_detection",
    force_class_names: Optional[Sequence[str]] = None,
    draw_boxes: bool = False,
    save_txt: bool = False,
    execution_device: str = "auto",
    progress_callback: Optional[Callable[[InferenceProgress], None]] = None,
    detection_callback: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
) -> InferenceSummary:
    import onnxruntime as ort

    start_t = time.perf_counter()

    model_path = model_path.expanduser().resolve()
    images_dir = images_dir.expanduser().resolve()
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        if images_dir.stat().st_dev != out_dir.stat().st_dev:
            raise ValueError(
                "硬链接要求输入与输出在同一文件系统："
                f"images_dir={images_dir} out_dir={out_dir}。"
                "请把输出目录放到 images 目录所在挂载下（例如 images/output/<run_id>）。"
            )
    except FileNotFoundError:
        pass

    sess_options = ort.SessionOptions()
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    requested_device = normalize_execution_device(execution_device)

    session = ort.InferenceSession(
        str(model_path),
        sess_options=sess_options,
        providers=build_ort_providers(requested_device),
    )
    providers = session.get_providers()
    cuda_enabled = "CUDAExecutionProvider" in providers
    logger.info("ONNXRuntime requested_device=%s providers=%s", requested_device, providers)
    if requested_device == "cpu":
        logger.info("已按请求使用 CPU 推理")
    elif not cuda_enabled:
        logger.warning("CUDAExecutionProvider 未启用（将使用 CPU 推理）")

    inputs = session.get_inputs()
    if not inputs:
        raise ValueError("ONNX 模型无输入")
    input_name = inputs[0].name
    input_type = getattr(inputs[0], "type", "tensor(float)")
    input_shape = inputs[0].shape or []
    fixed_batch = input_shape[0] if len(input_shape) >= 1 and isinstance(input_shape[0], int) else None
    fixed_h = input_shape[2] if len(input_shape) >= 3 and isinstance(input_shape[2], int) else None
    fixed_w = input_shape[3] if len(input_shape) >= 4 and isinstance(input_shape[3], int) else None
    input_dtype, input_scale, expects_float_input = resolve_ort_input_config(input_type)

    if fixed_batch is not None and int(batch) != int(fixed_batch):
        logger.warning("模型输入 batch 固定为 %d，将强制 batch=%d（当前=%d）", int(fixed_batch), int(fixed_batch), int(batch))
        batch = int(fixed_batch)

    if imgsz is None:
        if fixed_h and fixed_w:
            final_imgsz = (int(fixed_h), int(fixed_w))
        else:
            final_imgsz = (640, 640)
    else:
        final_imgsz = (int(imgsz), int(imgsz))
        if fixed_h and fixed_w and (final_imgsz[0] != int(fixed_h) or final_imgsz[1] != int(fixed_w)):
            logger.warning(
                "参数 imgsz=%s 与模型输入 HxW=%dx%d 不一致，将使用模型输入尺寸",
                final_imgsz,
                int(fixed_h),
                int(fixed_w),
            )
            final_imgsz = (int(fixed_h), int(fixed_w))

    class_names = _load_class_names(model_path, session)
    if not class_names and force_class_names:
        class_names = list(force_class_names)
    if class_names:
        logger.info("类别数: %d", len(class_names))
    else:
        logger.warning("未找到类别名，将使用 cls_id 作为类别名")

    total = 0
    written = 0
    hardlinked = 0
    copied = 0
    failed = 0
    txt_written = 0
    by_label: Dict[str, int] = {}
    created_dirs: Set[Path] = set()
    preprocess_sec = 0.0
    inference_sec = 0.0
    postprocess_sec = 0.0
    hardlink_sec = 0.0
    drawn = 0
    draw_sec = 0.0
    output_shape: Optional[List] = None
    recent_pre_batch_secs: Deque[float] = deque(maxlen=10)
    recent_infer_batch_secs: Deque[float] = deque(maxlen=10)
    recent_post_batch_secs: Deque[float] = deque(maxlen=10)
    recent_write_batch_secs: Deque[float] = deque(maxlen=10)

    def _prepare_batch(batch_paths: List[Path]) -> Tuple[List[Path], "object", float, int, List[Optional["object"]], List[Tuple[int, int]]]:
        import numpy as np

        t0 = time.perf_counter()
        real_count = len(batch_paths)
        pad = 0
        if fixed_batch is not None and real_count < used_batch:
            pad = used_batch - real_count

        batch_imgs = np.empty((used_batch, 3, final_imgsz[0], final_imgsz[1]), dtype=input_dtype)
        draw_imgs: List[Optional[np.ndarray]] = []
        orig_hws: List[Tuple[int, int]] = []

        image_futures = [decode_executor.submit(_prepare_one_image, p) for p in batch_paths]
        for idx, image_future in enumerate(image_futures):
            _path, img, draw_img, orig_hw = image_future.result()
            batch_imgs[idx, ...] = img
            draw_imgs.append(draw_img)
            orig_hws.append(orig_hw)
        if pad > 0:
            batch_imgs[real_count:used_batch, ...] = 0
            draw_imgs.extend([None] * pad)
        return batch_paths, batch_imgs, float(time.perf_counter() - t0), real_count, draw_imgs, orig_hws

    def _prepare_one_image(image_path: Path) -> Tuple[Path, "object", Optional["object"], Tuple[int, int]]:
        import cv2
        import numpy as np

        configure_cv2_runtime(cv2)
        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            img_bgr = np.zeros((final_imgsz[0], final_imgsz[1], 3), dtype=np.uint8)
        orig_hw = (int(img_bgr.shape[0]), int(img_bgr.shape[1]))
        img = _letterbox(img_bgr, imgsz=final_imgsz)
        draw_img = img.copy() if draw_boxes else None
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = np.transpose(img, (2, 0, 1))
        if expects_float_input:
            img = img.astype(input_dtype, copy=False) * input_scale
        else:
            img = img.astype(input_dtype, copy=False)
        return image_path, img, draw_img, orig_hw

    preprocess_workers = max(1, int(preprocess_workers))
    prefetch_batches = max(0, int(prefetch_batches))
    used_batch = int(batch)

    if not recursive:
        try:
            has_subdir = any(p.is_dir() for p in images_dir.iterdir())
        except FileNotFoundError:
            has_subdir = False
        if has_subdir:
            logger.info("检测到子目录，自动启用递归遍历（recursive=True）")
            recursive = True

    def _emit_progress(
        stage: str,
        processed: int,
        total_images: int,
        batch_size: int = 0,
        *,
        avg_pre_batch_sec: Optional[float] = None,
        avg_infer_batch_sec: Optional[float] = None,
        avg_post_batch_sec: Optional[float] = None,
        avg_write_batch_sec: Optional[float] = None,
    ) -> None:
        if progress_callback is None:
            return
        eta_sec: Optional[float] = None
        if total_images > 0 and avg_infer_batch_sec is not None and batch_size > 0:
            remaining = max(int(total_images) - int(processed), 0)
            remaining_batches = remaining / float(batch_size)
            eta_sec = max(remaining_batches * float(avg_infer_batch_sec), 0.0)
        progress_callback(
            InferenceProgress(
                stage=stage,
                processed=int(processed),
                total=int(total_images),
                remaining=max(int(total_images) - int(processed), 0) if int(total_images) > 0 else 0,
                batch_size=int(batch_size),
                elapsed_sec=max(0.0, float(time.perf_counter() - start_t)),
                avg_pre_batch_sec=avg_pre_batch_sec,
                avg_infer_batch_sec=avg_infer_batch_sec,
                avg_post_batch_sec=avg_post_batch_sec,
                avg_write_batch_sec=avg_write_batch_sec,
                eta_sec=eta_sec,
            )
        )

    logger.info("开始收集图片路径...")
    image_paths = collect_image_paths(
        images_dir,
        recursive=recursive,
        report_every=max(used_batch, 200),
        progress_callback=progress_callback,
    )
    total_images = len(image_paths)
    logger.info("图片路径收集完成：共 %d 张", total_images)
    _emit_progress("running", 0, total_images, 0)

    batch_iter = chunked(image_paths, used_batch)

    decode_executor = ThreadPoolExecutor(max_workers=preprocess_workers)
    executor = ThreadPoolExecutor(max_workers=max(1, prefetch_batches + 1))
    post_executor = ThreadPoolExecutor(max_workers=1)
    futures: Deque[Future] = deque()
    post_futures: Deque[Future] = deque()
    inferred_total = 0
    max_pending_post_batches = max(2, prefetch_batches + 2)

    def _mean_or_none(values: Deque[float]) -> Optional[float]:
        if not values:
            return None
        return sum(values) / float(len(values))

    def _merge_batch_work_summary(summary: BatchWorkSummary) -> None:
        nonlocal total, written, hardlinked, copied, failed, txt_written, drawn
        nonlocal postprocess_sec, hardlink_sec, draw_sec

        total += int(summary.total)
        written += int(summary.written)
        hardlinked += int(summary.hardlinked)
        copied += int(summary.copied)
        failed += int(summary.failed)
        txt_written += int(summary.txt_written)
        drawn += int(summary.drawn)
        postprocess_sec += float(summary.post_batch_sec)
        hardlink_sec += float(summary.write_batch_sec)
        draw_sec += float(summary.draw_batch_sec)
        recent_post_batch_secs.append(float(summary.post_batch_sec))
        recent_write_batch_secs.append(float(summary.write_batch_sec) + float(summary.draw_batch_sec))
        for label_name, count in summary.by_label.items():
            by_label[label_name] = by_label.get(label_name, 0) + int(count)

    def _build_batch_detections(
        *,
        batch_paths: List[Path],
        dets_for_draw: List[Optional[Tuple["object", "object", "object"]]],
        preds: List[Tuple[Path, List[str]]],
        orig_hws: List[Tuple[int, int]],
        drawn_paths: Dict[int, str],
        unmatched_label: str,
        class_names: Optional[Sequence[str]],
        out_dir: Path,
    ) -> List[Dict[str, Any]]:
        """组装每个 batch 内逐图检测结果，供 detection_callback 回调。"""
        import numpy as np

        results: List[Dict[str, Any]] = []
        for bi, src in enumerate(batch_paths):
            det = dets_for_draw[bi] if bi < len(dets_for_draw) else None
            height, width = orig_hws[bi] if bi < len(orig_hws) else (0, 0)
            rel_name = src.name
            detections: List[Dict[str, Any]] = []
            has_drawn = bi in drawn_paths
            drawn_path = drawn_paths.get(bi)
            if det is not None:
                xyxy, cls_ids, scores = det
                for idx in range(int(xyxy.shape[0])):
                    box = xyxy[idx]
                    cls_id_i = int(cls_ids[idx])
                    detections.append(
                        {
                            "label": sanitize_label(
                                _label_from_id(cls_id_i, class_names), fallback=str(cls_id_i)
                            ),
                            "confidence": float(scores[idx]),
                            "bbox": [
                                float(box[0]),
                                float(box[1]),
                                float(box[2]),
                                float(box[3]),
                            ],
                            "cls_id": cls_id_i,
                        }
                    )
            rel_parent: Path
            try:
                rel_parent = src.parent.relative_to(images_dir)
            except Exception:  # noqa: BLE001
                rel_parent = Path(".")
            results.append(
                {
                    "filename": rel_name,
                    "rel_path": str(src.relative_to(images_dir)) if src.is_absolute() else str(src),
                    "width": int(width),
                    "height": int(height),
                    "detections": detections,
                    "has_drawn": bool(has_drawn),
                    "drawn_path": drawn_path,
                }
            )
        return results

    def _process_batch_outputs(
        batch_paths: List[Path],
        out,
        real_count: int,
        draw_imgs: List[Optional["object"]],
        orig_hws: List[Tuple[int, int]],
    ) -> BatchWorkSummary:
        import numpy as np

        local_total = 0
        local_written = 0
        local_hardlinked = 0
        local_copied = 0
        local_failed = 0
        local_txt_written = 0
        local_drawn = 0
        local_by_label: Dict[str, int] = {}

        t_post = time.perf_counter()
        preds: List[Tuple[Path, List[str]]] = []
        dets_for_draw: List[Optional[Tuple["object", "object", "object"]]] = []
        dets_by_label_for_txt: List[Dict[str, Tuple["object", "object", Tuple[int, int]]]] = []
        for bi, p in enumerate(batch_paths[:real_count]):
            pred = out[bi]
            if pred.size == 0:
                preds.append((p, [unmatched_label]))
                dets_for_draw.append(None)
                dets_by_label_for_txt.append({})
                continue

            c = int(pred.shape[1])
            ncls = len(class_names) if class_names else None

            has_obj = False
            if ncls is not None and c == 5 + ncls:
                has_obj = True
            elif ncls is not None and c == 4 + ncls:
                has_obj = False
            elif c >= 6:
                has_obj = True

            if has_obj:
                obj = _maybe_sigmoid(pred[:, 4])
                cls_probs = _maybe_sigmoid(pred[:, 5:])
                cls_id = np.argmax(cls_probs, axis=1)
                cls_score = cls_probs[np.arange(cls_probs.shape[0]), cls_id]
                conf_v = obj * cls_score
            else:
                cls_probs = _maybe_sigmoid(pred[:, 4:])
                cls_id = np.argmax(cls_probs, axis=1)
                cls_score = cls_probs[np.arange(cls_probs.shape[0]), cls_id]
                conf_v = cls_score

            keep = conf_v >= float(conf)
            if allowed_class_ids is not None:
                allowed = np.isin(cls_id, np.fromiter(allowed_class_ids, dtype=np.int64))
                keep = keep & allowed

            if not np.any(keep):
                preds.append((p, [unmatched_label]))
                dets_for_draw.append(None)
                dets_by_label_for_txt.append({})
                continue

            pred = pred[keep]
            conf_f = conf_v[keep]
            cls_id_f = cls_id[keep]

            xy = pred[:, 0:2]
            wh = pred[:, 2:4]
            xyxy = np.concatenate([xy - wh / 2, xy + wh / 2], axis=1)

            keep_idx = _nms_xyxy(xyxy, conf_f, float(iou))
            xyxy = xyxy[keep_idx]
            conf_f = conf_f[keep_idx]
            cls_id_f = cls_id_f[keep_idx]
            unique_cls_ids = sorted({int(x) for x in cls_id_f.tolist()})
            labels = [
                sanitize_label(_label_from_id(cls_id_i, class_names), fallback=str(cls_id_i))
                for cls_id_i in unique_cls_ids
            ]
            det_map: Dict[str, Tuple["object", "object", Tuple[int, int]]] = {}
            for cls_id_i in unique_cls_ids:
                label_name = sanitize_label(_label_from_id(cls_id_i, class_names), fallback=str(cls_id_i))
                cls_mask = cls_id_f == int(cls_id_i)
                det_map[label_name] = (xyxy[cls_mask], cls_id_f[cls_mask], orig_hws[bi])
            preds.append((p, labels or [unmatched_label]))
            dets_for_draw.append((xyxy, cls_id_f, conf_f))
            dets_by_label_for_txt.append(det_map)
        post_batch_sec = float(time.perf_counter() - t_post)

        t_write = time.perf_counter()
        for bi, (src, labels) in enumerate(preds):
            local_total += 1
            try:
                rel_parent = src.parent.relative_to(images_dir)
            except Exception:  # noqa: BLE001
                rel_parent = Path(".")

            if labels == [unmatched_label]:
                safe_label = sanitize_label(unmatched_label, fallback=unmatched_label)
                local_by_label[safe_label] = local_by_label.get(safe_label, 0) + 1
                _ensure_label_tree(out_dir, safe_label, created_dirs)
                dest_dir = _category_images_dir(out_dir, safe_label, rel_parent)
                if dest_dir not in created_dirs:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    created_dirs.add(dest_dir)
                dest = dest_dir / src.name
                try:
                    mode = hardlink_or_copy(src, dest, copy_fallback=copy_fallback)
                except Exception:
                    local_failed += 1
                    raise
                else:
                    local_written += 1
                    if mode == "hardlink":
                        local_hardlinked += 1
                    elif mode == "copy":
                        local_copied += 1
                continue

            det_map = dets_by_label_for_txt[bi] if bi < len(dets_by_label_for_txt) else {}
            for label in labels:
                safe_label = sanitize_label(label, fallback=unmatched_label)
                local_by_label[safe_label] = local_by_label.get(safe_label, 0) + 1
                _ensure_label_tree(out_dir, safe_label, created_dirs)

                image_dir = _category_images_dir(out_dir, safe_label, rel_parent)
                if image_dir not in created_dirs:
                    image_dir.mkdir(parents=True, exist_ok=True)
                    created_dirs.add(image_dir)
                dest = image_dir / src.name
                try:
                    mode = hardlink_or_copy(src, dest, copy_fallback=copy_fallback)
                except Exception:
                    local_failed += 1
                    raise
                else:
                    local_written += 1
                    if mode == "hardlink":
                        local_hardlinked += 1
                    elif mode == "copy":
                        local_copied += 1

                if save_txt:
                    det = det_map.get(safe_label)
                    if det is None:
                        continue
                    txt_dir = _category_labels_dir(out_dir, safe_label, rel_parent)
                    if txt_dir not in created_dirs:
                        txt_dir.mkdir(parents=True, exist_ok=True)
                        created_dirs.add(txt_dir)
                    txt_path = txt_dir / f"{src.stem}.txt"
                    boxes_xyxy, cls_ids, orig_hw = det
                    _write_yolo_txt(txt_path, boxes_xyxy, cls_ids, orig_hw=orig_hw, imgsz=final_imgsz)
                    local_txt_written += 1
        write_batch_sec = float(time.perf_counter() - t_write)

        draw_batch_sec = 0.0
        drawn_paths: Dict[int, str] = {}
        if draw_boxes:
            import cv2

            t_draw = time.perf_counter()
            for bi, src in enumerate(batch_paths[:real_count]):
                det = dets_for_draw[bi] if bi < len(dets_for_draw) else None
                canvas = draw_imgs[bi] if bi < len(draw_imgs) else None
                if canvas is None:
                    continue
                if det is not None:
                    xyxy, cls_ids, scores = det
                    _draw_boxes(canvas, xyxy, cls_ids, scores, class_names)

                try:
                    rel_parent = src.parent.relative_to(images_dir)
                except Exception:  # noqa: BLE001
                    rel_parent = Path(".")

                if det is None:
                    labels = [unmatched_label]
                else:
                    cls_ids = det[1]
                    unique_cls_ids = sorted({int(x) for x in cls_ids.tolist()})
                    labels = [
                        sanitize_label(_label_from_id(cls_id_i, class_names), fallback=str(cls_id_i))
                        for cls_id_i in unique_cls_ids
                    ] or [unmatched_label]

                for label in labels:
                    safe_label = sanitize_label(label, fallback=unmatched_label)
                    draw_label = f"{safe_label}_画框"
                    dest_dir = out_dir / draw_label / "images"
                    if rel_parent != Path("."):
                        dest_dir = dest_dir / rel_parent
                    if dest_dir not in created_dirs:
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        created_dirs.add(dest_dir)

                    out_name = _safe_annotated_name(src)
                    dest = dest_dir / out_name
                    dest = unique_path(dest)
                    ok = cv2.imwrite(str(dest), canvas)
                    if ok:
                        local_drawn += 1
                        drawn_paths[bi] = str(dest)
                    else:
                        local_failed += 1
                        raise ValueError(f"画框图片写入失败: {dest}")

            draw_batch_sec = float(time.perf_counter() - t_draw)

        if detection_callback is not None:
            detection_callback(_build_batch_detections(
                batch_paths=batch_paths[:real_count],
                dets_for_draw=dets_for_draw,
                preds=preds,
                orig_hws=orig_hws,
                drawn_paths=drawn_paths,
                unmatched_label=unmatched_label,
                class_names=class_names,
                out_dir=out_dir,
            ))

        return BatchWorkSummary(
            total=local_total,
            written=local_written,
            hardlinked=local_hardlinked,
            copied=local_copied,
            failed=local_failed,
            txt_written=local_txt_written,
            drawn=local_drawn,
            by_label=local_by_label,
            post_batch_sec=post_batch_sec,
            write_batch_sec=write_batch_sec,
            draw_batch_sec=draw_batch_sec,
        )

    def _submit_next() -> None:
        try:
            b = next(batch_iter)
        except StopIteration:
            return
        futures.append(executor.submit(_prepare_batch, b))

    try:
        _submit_next()
        for _ in range(prefetch_batches):
            _submit_next()

        while futures:
            batch_paths, inp, t_pre, real_count, draw_imgs, orig_hws = futures.popleft().result()
            preprocess_sec += float(t_pre)
            recent_pre_batch_secs.append(float(t_pre))
            _submit_next()

            avg_pre_batch_sec = None
            if recent_pre_batch_secs:
                avg_pre_batch_sec = sum(recent_pre_batch_secs) / float(len(recent_pre_batch_secs))
            avg_infer_batch_sec = None
            if recent_infer_batch_secs:
                avg_infer_batch_sec = sum(recent_infer_batch_secs) / float(len(recent_infer_batch_secs))
            if inferred_total == 0:
                logger.info(
                    "开始第1个 batch 推理：batch_size=%d input_shape=%s providers=%s",
                    real_count,
                    list(getattr(inp, "shape", [])),
                    providers,
                )
                _emit_progress(
                    "warming_up",
                    total,
                    total_images,
                    real_count,
                    avg_pre_batch_sec=avg_pre_batch_sec,
                    avg_infer_batch_sec=avg_infer_batch_sec,
                )

            t0 = time.perf_counter()
            outputs = session.run(None, {input_name: inp})
            infer_batch_sec = float(time.perf_counter() - t0)
            inference_sec += infer_batch_sec
            recent_infer_batch_secs.append(infer_batch_sec)
            if inferred_total == 0:
                logger.info("完成第1个 batch 推理，耗时 %.2fs", infer_batch_sec)
            if not outputs:
                raise ValueError("ONNX 推理无输出")

            out_raw = outputs[0]
            if output_shape is None:
                try:
                    output_shape = list(out_raw.shape)  # type: ignore[attr-defined]
                except Exception:  # noqa: BLE001
                    output_shape = None

            out = out_raw
            if out.ndim == 2:
                import numpy as np

                out = np.expand_dims(out, axis=0)
            out = _normalize_yolo_output(out)
            if out.shape[2] < 6:
                raise ValueError(f"不支持的输出形状: {out.shape}（期望 [B,N,5+num_cls]）")
            inferred_total += real_count
            post_futures.append(
                post_executor.submit(
                    _process_batch_outputs,
                    batch_paths,
                    out[:real_count].copy(),
                    real_count,
                    draw_imgs[:real_count],
                    orig_hws[:real_count],
                )
            )

            while len(post_futures) > max_pending_post_batches:
                summary = post_futures.popleft().result()
                _merge_batch_work_summary(summary)

            if total % 2000 == 0 and total > 0:
                logger.info(
                    "已处理 %d/%d 张（推理已完成 %d，剩余 %d，hardlink=%d copy=%d failed=%d，workers=%d prefetch=%d）",
                    total,
                    total_images,
                    inferred_total,
                    max(total_images - total, 0),
                    hardlinked,
                    copied,
                    failed,
                    preprocess_workers,
                    prefetch_batches,
                )

            _emit_progress(
                "running",
                max(total, inferred_total),
                total_images,
                real_count,
                avg_pre_batch_sec=_mean_or_none(recent_pre_batch_secs),
                avg_infer_batch_sec=_mean_or_none(recent_infer_batch_secs),
                avg_post_batch_sec=_mean_or_none(recent_post_batch_secs),
                avg_write_batch_sec=_mean_or_none(recent_write_batch_secs),
            )

        while post_futures:
            summary = post_futures.popleft().result()
            _merge_batch_work_summary(summary)
    finally:
        executor.shutdown(wait=True, cancel_futures=False)
        decode_executor.shutdown(wait=True, cancel_futures=False)
        post_executor.shutdown(wait=True, cancel_futures=False)

    elapsed_sec = max(0.0, float(time.perf_counter() - start_t))
    final_avg_pre_batch_sec = None
    if recent_pre_batch_secs:
        final_avg_pre_batch_sec = sum(recent_pre_batch_secs) / float(len(recent_pre_batch_secs))
    final_avg_infer_batch_sec = None
    if recent_infer_batch_secs:
        final_avg_infer_batch_sec = sum(recent_infer_batch_secs) / float(len(recent_infer_batch_secs))
    final_avg_post_batch_sec = None
    if recent_post_batch_secs:
        final_avg_post_batch_sec = sum(recent_post_batch_secs) / float(len(recent_post_batch_secs))
    final_avg_write_batch_sec = None
    if recent_write_batch_secs:
        final_avg_write_batch_sec = sum(recent_write_batch_secs) / float(len(recent_write_batch_secs))
    _emit_progress(
        "done",
        total,
        total_images,
        used_batch,
        avg_pre_batch_sec=final_avg_pre_batch_sec,
        avg_infer_batch_sec=final_avg_infer_batch_sec,
        avg_post_batch_sec=final_avg_post_batch_sec,
        avg_write_batch_sec=final_avg_write_batch_sec,
    )
    return InferenceSummary(
        total=total,
        written=written,
        hardlinked=hardlinked,
        copied=copied,
        failed=failed,
        txt_written=int(txt_written),
        elapsed_sec=elapsed_sec,
        preprocess_sec=float(preprocess_sec),
        inference_sec=float(inference_sec),
        postprocess_sec=float(postprocess_sec),
        hardlink_sec=float(hardlink_sec),
        drawn=int(drawn),
        draw_sec=float(draw_sec),
        providers=list(providers),
        cuda_enabled=bool(cuda_enabled),
        requested_device=requested_device,
        used_batch=used_batch,
        used_imgsz=final_imgsz,
        input_shape=list(input_shape),
        output_shape=output_shape,
        by_label=by_label,
        out_dir=str(out_dir),
    )
