from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from .exporting import export_zip_by_label
from .inference.yolov5_onnx import YoloV5Onnx
from .logging_utils import get_logger
from .settings import Settings
from .storage import (
    count_images,
    create_run,
    finish_run,
    get_image_paths_by_label,
    init_db,
    iter_image_paths,
    iter_image_paths_without_model,
    label_counts,
    list_labels,
    upsert_images,
    upsert_model,
    write_predictions_top1,
)
from .utils import IMAGE_EXTS, ensure_dir, iter_images, resolve_path, sanitize_label


logger = get_logger(__name__)


NO_DETECTION_LABEL = "no_detection"


def ensure_app_state(settings: Settings) -> None:
    ensure_dir(settings.data_dir)
    ensure_dir(settings.exports_dir)
    init_db(settings.db_path)


def sync_images_from_dir(
    settings: Settings,
    images_dir: str,
    recursive: bool = True,
    batch_size: int = 1000,
    progress: Optional[Callable[[float, str], None]] = None,
) -> Tuple[str, List[List[object]]]:
    ensure_app_state(settings)

    root = resolve_path(images_dir, None)
    if not root.exists():
        raise FileNotFoundError(f"图片目录不存在: {root}")

    if recursive:
        it = iter_images(root)
    else:
        it = (
            str(p)
            for p in root.iterdir()
            if p.is_file() and p.suffix.lower() in {e.lower() for e in IMAGE_EXTS}
        )

    seen_total = 0
    inserted_total = 0
    buffer: List[str] = []

    for path in it:
        buffer.append(path)
        if len(buffer) >= int(batch_size):
            seen, inserted = upsert_images(settings.db_path, buffer)
            seen_total += seen
            inserted_total += inserted
            buffer = []
            if progress is not None:
                progress(0.0, f"同步中：已扫描 {seen_total}，新增 {inserted_total}")

    if buffer:
        seen, inserted = upsert_images(settings.db_path, buffer)
        seen_total += seen
        inserted_total += inserted

    total_db = count_images(settings.db_path)
    msg = f"同步完成：已扫描 {seen_total}，新增 {inserted_total}，库内总数 {total_db}"
    rows = [["scanned", seen_total], ["added", inserted_total], ["total_in_db", total_db]]
    logger.info(msg)
    return msg, rows


def _model_id_from_filename(model_file: str) -> str:
    return sanitize_label(Path(model_file).stem, fallback="model")


def run_inference_top1(
    settings: Settings,
    model_file: str,
    model_id: Optional[str],
    confidence: float,
    batch_size: int,
    only_untagged: bool,
    overwrite: bool,
    iou_thres: float = 0.45,
    progress: Optional[Callable[[float, str], None]] = None,
) -> Tuple[str, List[List[object]]]:
    ensure_app_state(settings)

    model_path = resolve_path(model_file, settings.models_dir)
    if model_path.suffix.lower() != ".onnx":
        raise ValueError("仅支持 .onnx 模型（本项目已移除 .pt/PyTorch 推理）")
    if not model_path.exists():
        raise FileNotFoundError(f"模型文件不存在: {model_path}")

    mid = sanitize_label((model_id or "").strip(), fallback=_model_id_from_filename(model_path.name))

    engine = YoloV5Onnx(model_path=model_path, imgsz=settings.default_imgsz)
    upsert_model(
        settings.db_path,
        model_id=mid,
        onnx_path=str(model_path),
        imgsz=settings.default_imgsz,
        class_names=engine.class_names,
    )

    run_id = create_run(settings.db_path, model_id=mid, conf=float(confidence))

    if only_untagged:
        paths_iter = iter_image_paths_without_model(settings.db_path, mid)
    else:
        paths_iter = iter_image_paths(settings.db_path)

    # 先 materialize 一次，便于进度条（后续可优化为估算/分段统计）
    paths = list(paths_iter)
    total = len(paths)
    if total == 0:
        finish_run(settings.db_path, run_id, status="done", error=None)
        return "无待处理图片（请先同步图片，或关闭“仅未处理”）", []

    processed = 0
    counter: Counter[str] = Counter()
    try:
        for idx in range(0, total, int(batch_size)):
            batch = paths[idx : idx + int(batch_size)]
            preds = engine.predict_top1(batch, conf_thres=float(confidence), iou_thres=float(iou_thres))
            # preds: (path, safe_label, conf)
            written = write_predictions_top1(
                settings.db_path,
                run_id=run_id,
                model_id=mid,
                items=[
                    (p, lbl if lbl else NO_DETECTION_LABEL, conf)
                    for (p, lbl, conf) in preds
                ],
                overwrite=bool(overwrite),
            )
            processed += written
            for _, lbl, _ in preds:
                counter[lbl or NO_DETECTION_LABEL] += 1
            if progress is not None:
                progress(processed / max(total, 1), f"推理中：{processed}/{total}")

        finish_run(settings.db_path, run_id, status="done", error=None)
    except Exception as exc:  # noqa: BLE001
        finish_run(settings.db_path, run_id, status="error", error=str(exc))
        raise

    rows = [[k, int(v)] for k, v in counter.most_common()]
    msg = f"推理完成：model_id={mid} processed={processed} total={total} labels={len(counter)}"
    logger.info(msg)
    return msg, rows


def list_available_labels(settings: Settings, model_id: Optional[str] = None) -> List[str]:
    ensure_app_state(settings)
    labels = list_labels(settings.db_path, model_id=model_id)
    return labels


def get_label_counts(settings: Settings, model_id: Optional[str] = None) -> List[List[object]]:
    ensure_app_state(settings)
    return [[lbl, cnt] for lbl, cnt in label_counts(settings.db_path, model_id=model_id)]


def preview_images_by_label(
    settings: Settings,
    label: str,
    model_id: Optional[str] = None,
    limit: int = 60,
    offset: int = 0,
) -> List[Tuple[str, str]]:
    ensure_app_state(settings)
    paths = get_image_paths_by_label(
        settings.db_path,
        label=label,
        model_id=model_id,
        limit=int(limit),
        offset=int(offset),
    )
    return [(p, Path(p).name) for p in paths]


def export_label_zip(
    settings: Settings,
    label: str,
    model_id: Optional[str] = None,
    zip_name: Optional[str] = None,
    prefer_hardlink: bool = True,
    progress: Optional[Callable[[float, str], None]] = None,
) -> Tuple[str, str]:
    ensure_app_state(settings)

    # 全量导出该 label（不分页）
    paths = get_image_paths_by_label(settings.db_path, label=label, model_id=model_id, limit=10_000_000, offset=0)

    def cb(frac: float, desc: str) -> None:
        if progress is not None:
            progress(frac, desc)

    msg, zip_path = export_zip_by_label(
        image_paths=paths,
        label=label,
        exports_dir=settings.exports_dir,
        zip_name=zip_name,
        prefer_hardlink=prefer_hardlink,
        progress=cb,
    )
    return msg, str(zip_path)
