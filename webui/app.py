from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path
from typing import Generator, List, Optional, Tuple

import gradio as gr

from webui.archive_ingest import extract_upload_archive
from webui.job_manager import get_job_manager
from webui.processing import (
    PackageProgress,
    format_seconds_human,
    InferenceProgress,
    InferenceSummary,
    PackageSummary,
    package_output_dir,
)
from webui.coco import COCO80_NAMES, COCO80_NAME_TO_ID
from webui.utils import (
    data_dir_from_env,
    ensure_relative,
    get_logger,
    list_models,
    now_run_id,
    resolve_images_dir,
    sanitize_filename,
    unique_path,
)


logger = get_logger(__name__)

IMAGES_DIR = data_dir_from_env("IMAGES_DIR", "/data/images")
MODELS_DIR = data_dir_from_env("MODELS_DIR", "/data/models")
# 宿主机侧的 images 目录（被挂载到容器内 IMAGES_DIR），用于把用户输入的宿主机
# 绝对路径换算为容器内路径。未配置时回退为 IMAGES_DIR 本身。
HOST_IMAGES_DIR = data_dir_from_env("HOST_IMAGES_DIR", str(IMAGES_DIR))


def _ensure_dirs() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    (IMAGES_DIR / "output").mkdir(parents=True, exist_ok=True)
    (IMAGES_DIR / "uploads").mkdir(parents=True, exist_ok=True)


def _model_choices() -> List[str]:
    return list_models(MODELS_DIR)


def _imageset_choices() -> List[str]:
    """仅枚举 IMAGES_DIR（被挂载目录）的直接子目录，和根目录无关。

    排除 output/uploads 运行产物，避免列表里混入系统目录。
    """
    choices = []
    for name in (list(IMAGES_DIR.iterdir()) if IMAGES_DIR.exists() else []):
        if not name.is_dir():
            continue
        if name.name in ("output", "uploads"):
            continue
        choices.append(str(name))
    return sorted(choices)


def _load_names_for_model(model_name: str) -> List[str]:
    model_name = (model_name or "").strip()
    if not model_name:
        return []
    model_path = (MODELS_DIR / model_name).resolve()
    if not model_path.exists():
        return []

    for ext in (".names", ".txt"):
        p = model_path.with_suffix(ext)
        if p.exists():
            lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()]
            return [ln for ln in lines if ln]

    json_path = model_path.with_suffix(".json")
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("names"), list):
                return [str(x) for x in data["names"]]
            if isinstance(data, list):
                return [str(x) for x in data]
        except Exception:  # noqa: BLE001
            return []

    return []


def _update_class_controls(model_name: str, model_type: str):
    model_type = (model_type or "").strip()
    if model_type == "官方COCO":
        return (
            gr.update(visible=True),
            gr.update(visible=False, choices=[], value=[]),
            gr.update(visible=False, value=""),
        )

    names = _load_names_for_model(model_name)
    if names:
        return (
            gr.update(visible=False, value=[]),
            gr.update(visible=True, choices=names, value=[]),
            gr.update(visible=False, value=""),
        )
    hint = (
        "未找到该模型的类别名 sidecar。请在 `models/` 下放置同名文件："
        f"`{Path(model_name).with_suffix('.names').name}`（每行一个类别名）或 `.txt/.json`。"
    )
    return (
        gr.update(visible=False, value=[]),
        gr.update(visible=True, choices=[], value=[]),
        gr.update(visible=True, value=hint),
    )


def upload_model(file_obj, overwrite: bool) -> Tuple[str, gr.Dropdown]:
    _ensure_dirs()
    if file_obj is None:
        return "未选择文件", gr.Dropdown(choices=_model_choices())

    src_path = Path(getattr(file_obj, "name", "")).expanduser().resolve()
    if not src_path.exists():
        return f"上传文件不可用: {src_path}", gr.Dropdown(choices=_model_choices())

    name = sanitize_filename(src_path.name)
    if not name.lower().endswith(".onnx"):
        return "仅支持上传 .onnx 模型", gr.Dropdown(choices=_model_choices())

    dest = MODELS_DIR / name
    if dest.exists() and not overwrite:
        return f"模型已存在（未覆盖）: {dest.name}", gr.Dropdown(choices=_model_choices(), value=dest.name)
    if dest.exists() and overwrite:
        dest.unlink()
    shutil.copy2(str(src_path), str(dest))
    return f"模型已保存: {dest.name}", gr.Dropdown(choices=_model_choices(), value=dest.name)


def _looks_like_zip(path: Path) -> bool:
    return path.suffix.lower() == ".zip"


def resolve_images_input(value: str) -> Optional[Path]:
    return resolve_images_dir(value, IMAGES_DIR, host_images_dir=HOST_IMAGES_DIR)


def upload_images(
    files: Optional[List],
    target_subdir: str,
    rename_on_conflict: bool,
) -> Generator[Tuple[str, str], None, None]:
    """上传图片或 .zip 压缩包。

    - 图片：逐文件复制到目标目录（沿用旧行为）。
    - .zip：后台自动解压（仅保留受支持的图片扩展名），完成后把解压目录（相对 images/）
      自动回填到推理输入框。
    """
    _ensure_dirs()
    if not files:
        yield "未选择文件", ""
        return

    rel = ensure_relative(target_subdir)
    if rel:
        dest_dir = IMAGES_DIR / rel
    else:
        dest_dir = IMAGES_DIR / "uploads" / now_run_id()
    dest_dir.mkdir(parents=True, exist_ok=True)

    zip_count = 0
    img_count = 0
    skipped = 0
    first_zip_rel = ""
    final_rel = ""

    for f in files:
        src_path = Path(getattr(f, "name", "")).expanduser().resolve()
        if not src_path.exists():
            continue

        if _looks_like_zip(src_path):
            zip_count += 1
            # 压缩包每次重新上传并解压到一个独立子目录，避免互相覆盖。
            extract_dir = dest_dir / (src_path.stem or now_run_id())
            extract_dir = unique_path(extract_dir)
            try:
                extract_upload_archive(src_path, extract_dir)
            except Exception as exc:  # noqa: BLE001
                logger.exception("压缩包解压失败")
                yield f"压缩包解压失败: {exc}", ""
                return
            if not first_zip_rel:
                try:
                    first_zip_rel = str(extract_dir.resolve().relative_to(IMAGES_DIR))
                except Exception:  # noqa: BLE001
                    first_zip_rel = str(extract_dir)
            continue

        # 普通图片：逐文件复制
        dest = dest_dir / sanitize_filename(src_path.name)
        if dest.exists() and not rename_on_conflict:
            skipped += 1
            continue
        if dest.exists() and rename_on_conflict:
            dest = unique_path(dest)
        shutil.copy2(str(src_path), str(dest))
        img_count += 1

    # 回填目录：有图片（含混合上传）回填公共父目录 dest_dir；仅 zip 时回填首个解压目录。
    if img_count > 0:
        try:
            final_rel = str(dest_dir.resolve().relative_to(IMAGES_DIR))
        except Exception:  # noqa: BLE001
            final_rel = str(dest_dir)
    else:
        final_rel = first_zip_rel

    if img_count > 0 and zip_count > 0:
        summary = f"已保存图片: {img_count}，解压压缩包: {zip_count}，跳过: {skipped}，目录: {final_rel}（图片在根目录，zip 已解压到子目录）"
    else:
        summary = f"已保存图片: {img_count}，解压压缩包: {zip_count}，跳过: {skipped}，目录: {final_rel}"
    yield summary, final_rel


def run_job(
    model_name: str,
    images_rel: str,
    model_type: str,
    focus_coco_classes: List[str],
    focus_custom_classes: List[str],
    unmatched_label: str,
    conf: float,
    iou: float,
    batch: int,
    recursive: bool,
    imgsz: Optional[int],
    strict_hardlink: bool,
    do_package: bool,
    preprocess_workers: int,
    prefetch_batches: int,
    draw_boxes: bool,
    save_txt: bool,
    use_cpu: bool,
    progress=gr.Progress(),
) -> Generator[Tuple[str, Optional[str], str, float, float], None, None]:
    """运行推理。流式产出：(状态文本, zip下载, 输出目录, 推理进度, 打包进度)。"""
    _ensure_dirs()
    model_name = (model_name or "").strip()
    images_rel = (images_rel or "").strip()

    if not model_name:
        yield "请先选择/上传模型", None, "", 0.0, 0.0
        return
    model_path = (MODELS_DIR / model_name).resolve()
    if not model_path.exists():
        yield f"模型不存在: {model_name}", None, "", 0.0, 0.0
        return

    images_dir = resolve_images_input(images_rel)
    if images_dir is None:
        yield "图片目录不能为空", None, "", 0.0, 0.0
        return
    if not images_dir.exists():
        yield (
            f"图片目录不存在: {images_rel}（当前解析为 {images_dir}）",
            None,
            "",
            0.0,
            0.0,
        )
        return

    run_id = now_run_id()
    out_dir = (IMAGES_DIR / "output" / run_id).resolve()

    unmatched_label = (unmatched_label or "no_detection").strip() or "no_detection"
    model_type = (model_type or "官方COCO").strip()

    focus_names: List[str] = []
    class_names: Optional[List[str]] = None
    if model_type == "官方COCO":
        class_names = list(COCO80_NAMES)
        focus_names = list(focus_coco_classes or [])
    else:
        class_names = _load_names_for_model(model_name) or None
        focus_names = list(focus_custom_classes or [])

    allowed_ids = None
    if focus_names and class_names:
        allowed_ids = set()
        for name in focus_names:
            try:
                allowed_ids.add(int(class_names.index(name)))
            except ValueError:
                continue

    execution_device = "cpu" if bool(use_cpu) else "auto"
    progress_status = {"text": "准备开始推理...", "processed": 0, "total": 0}
    pkg_status = {"pct": 0.0, "desc": ""}
    job_manager = get_job_manager()

    def _format_progress_text(progress_info: InferenceProgress) -> str:
        device_text = "CPU" if execution_device == "cpu" else "GPU优先"
        pre_text = format_seconds_human(progress_info.avg_pre_batch_sec)
        infer_text = format_seconds_human(progress_info.avg_infer_batch_sec)
        post_text = format_seconds_human(progress_info.avg_post_batch_sec)
        write_text = format_seconds_human(progress_info.avg_write_batch_sec)
        if progress_info.stage == "counting":
            if progress_info.total > 0:
                return f"正在统计图片，总计 {progress_info.total} 张，推理设备：{device_text}"
            return f"正在统计图片，已扫描 {progress_info.processed} 张，推理设备：{device_text}"
        if progress_info.stage == "warming_up":
            eta_text = format_seconds_human(progress_info.eta_sec)
            return (
                f"正在预热首个batch：已处理 {progress_info.processed}/{progress_info.total} 张，"
                f"当前批次 {progress_info.batch_size} 张，最近10个batch均值 pre={pre_text} infer={infer_text} post={post_text} write={write_text}，"
                f"预计剩余 {eta_text}，推理设备：{device_text}"
            )
        if progress_info.stage == "done":
            return (
                f"推理完成：已处理 {progress_info.processed}/{progress_info.total} 张，剩余 0 张，"
                f"最近10个batch均值 pre={pre_text} infer={infer_text} post={post_text} write={write_text}，推理设备：{device_text}"
            )

        total_images = progress_info.total
        processed = progress_info.processed
        remaining = progress_info.remaining
        eta_text = format_seconds_human(progress_info.eta_sec)
        if total_images > 0:
            pct = (float(processed) / float(total_images)) * 100.0
            return (
                f"推理中：已处理 {processed}/{total_images} 张，剩余 {remaining} 张，"
                f"当前批次 {progress_info.batch_size} 张，最近10个batch均值 pre={pre_text} infer={infer_text} post={post_text} write={write_text}，"
                f"预计剩余 {eta_text}，进度 {pct:.1f}%，推理设备：{device_text}"
            )
        return f"推理中：已处理 {processed} 张，推理设备：{device_text}"

    def _on_progress(progress_info: InferenceProgress) -> None:
        progress_status["text"] = _format_progress_text(progress_info)
        progress_status["processed"] = progress_info.processed
        progress_status["total"] = progress_info.total
        if progress_info.stage == "counting":
            progress(None, desc=progress_status["text"])
            return

        total_images = int(progress_info.total)
        if total_images > 0:
            progress(
                min(max(float(progress_info.processed) / float(total_images), 0.0), 1.0),
                desc=progress_status["text"],
            )
        else:
            progress(None, desc=progress_status["text"])

    def _infer_pct() -> float:
        total = int(progress_status["total"])
        if total > 0:
            return min(max(float(progress_status["processed"]) / float(total), 0.0), 1.0)
        return 0.0

    # 产出初值：推理条归零，打包条不出现（0.0）。
    yield progress_status["text"], None, "", 0.0, 0.0

    try:
        job_id = job_manager.submit(
            {
                "model_path": str(model_path),
                "images_dir": str(images_dir),
                "out_dir": str(out_dir),
                "recursive": bool(recursive),
                "batch": int(batch),
                "imgsz": int(imgsz) if imgsz else None,
                "conf": float(conf),
                "iou": float(iou),
                "copy_fallback": not bool(strict_hardlink),
                "preprocess_workers": int(preprocess_workers),
                "prefetch_batches": int(prefetch_batches),
                "allowed_class_ids": sorted(allowed_ids) if allowed_ids is not None else None,
                "unmatched_label": unmatched_label,
                "force_class_names": list(class_names) if class_names else None,
                "draw_boxes": bool(draw_boxes),
                "save_txt": bool(save_txt),
                "execution_device": execution_device,
            }
        )

        summary_data = None
        error_message = None
        while True:
            event = job_manager.poll_event(job_id, timeout_sec=0.2)
            if event is None:
                if job_manager.job_done(job_id):
                    break
                continue

            event_type = event.get("type")
            data = event.get("data") or {}
            if event_type == "progress":
                progress_info = InferenceProgress(
                    stage=str(data.get("stage", "running")),
                    processed=int(data.get("processed", 0)),
                    total=int(data.get("total", 0)),
                    remaining=int(data.get("remaining", 0)),
                    batch_size=int(data.get("batch_size", 0)),
                    elapsed_sec=float(data.get("elapsed_sec", 0.0)),
                    avg_pre_batch_sec=data.get("avg_pre_batch_sec"),
                    avg_infer_batch_sec=data.get("avg_infer_batch_sec"),
                    avg_post_batch_sec=data.get("avg_post_batch_sec"),
                    avg_write_batch_sec=data.get("avg_write_batch_sec"),
                    eta_sec=data.get("eta_sec"),
                )
                _on_progress(progress_info)
                yield progress_status["text"], None, "", _infer_pct(), 0.0
            elif event_type == "result":
                summary_data = data.get("summary")
            elif event_type == "error":
                error_message = str(data.get("message", "推理失败"))

        job_manager.drop(job_id)
        if error_message:
            raise RuntimeError(error_message)
        if not isinstance(summary_data, dict):
            raise RuntimeError("推理任务未返回结果")
        summary = InferenceSummary(
            total=int(summary_data["total"]),
            written=int(summary_data["written"]),
            hardlinked=int(summary_data["hardlinked"]),
            copied=int(summary_data["copied"]),
            failed=int(summary_data["failed"]),
            txt_written=int(summary_data["txt_written"]),
            elapsed_sec=float(summary_data["elapsed_sec"]),
            preprocess_sec=float(summary_data["preprocess_sec"]),
            inference_sec=float(summary_data["inference_sec"]),
            postprocess_sec=float(summary_data["postprocess_sec"]),
            hardlink_sec=float(summary_data["hardlink_sec"]),
            drawn=int(summary_data["drawn"]),
            draw_sec=float(summary_data["draw_sec"]),
            providers=list(summary_data["providers"]),
            cuda_enabled=bool(summary_data["cuda_enabled"]),
            requested_device=str(summary_data["requested_device"]),
            used_batch=int(summary_data["used_batch"]),
            used_imgsz=tuple(summary_data["used_imgsz"]),
            input_shape=list(summary_data["input_shape"]),
            output_shape=list(summary_data["output_shape"]) if summary_data.get("output_shape") is not None else None,
            by_label=dict(summary_data["by_label"]),
            out_dir=str(summary_data["out_dir"]),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("推理失败")
        fail_text = progress_status["text"]
        if fail_text:
            fail_text = f"{fail_text}\n推理失败: {exc}"
        else:
            fail_text = f"推理失败: {exc}"
        yield fail_text, None, "", 0.0, 0.0
        return

    # 推理完成：推理进度条定满，打包条仍为 0。
    yield progress_status["text"], None, "", 1.0, 0.0

    zip_tmp: Optional[str] = None
    zip_saved_rel = ""
    if do_package:
        def _on_package_progress(pkg_info: PackageProgress) -> None:
            if pkg_info.total > 0:
                pkg_status["pct"] = min(max(float(pkg_info.processed) / float(pkg_info.total), 0.0), 1.0)
            else:
                pkg_status["pct"] = 0.0
            pkg_status["desc"] = f"打包中：{pkg_info.processed}/{pkg_info.total} 个文件，进度 {pkg_status['pct'] * 100:.1f}%"

        # 在后台线程执行打包，生成器轮询共享状态，使打包进度条实时更新
        # （同步阻塞调用会让 yield 无法触发，进度条卡在初值）。
        pkg_result: List[PackageSummary] = []
        pkg_error: List[BaseException] = []

        def _run_package() -> None:
            try:
                pkg_result.append(
                    package_output_dir(
                        Path(summary.out_dir),
                        progress_callback=_on_package_progress,
                    )
                )
            except BaseException as exc:  # noqa: BLE001
                pkg_error.append(exc)

        _on_package_progress(PackageProgress(processed=0, total=0))
        yield progress_status["text"], None, "", 1.0, pkg_status["pct"]

        t = threading.Thread(target=_run_package, daemon=True, name="yolo-package")
        t.start()
        while t.is_alive():
            t.join(timeout=0.2)
            yield progress_status["text"], None, "", 1.0, pkg_status["pct"]

        if pkg_error:
            logger.exception("打包失败")
            zip_tmp = None
            zip_saved_rel = f"打包失败: {pkg_error[0]}"
            yield progress_status["text"], None, "", 1.0, 0.0
        else:
            pkg = pkg_result[0]
            zip_tmp = pkg.zip_tmp_path
            try:
                zip_saved_rel = str(Path(pkg.zip_saved_path).resolve().relative_to(IMAGES_DIR))
            except Exception:  # noqa: BLE001
                zip_saved_rel = pkg.zip_saved_path
            yield progress_status["text"], None, "", 1.0, 1.0

    by_label = sorted(summary.by_label.items(), key=lambda x: (-x[1], x[0]))
    stats = "，".join([f"{k}:{v}" for k, v in by_label])

    out_path = Path(summary.out_dir)
    try:
        out_rel = str(out_path.relative_to(IMAGES_DIR))
    except Exception:  # noqa: BLE001
        out_rel = ""

    out_display = out_rel or summary.out_dir
    fps = (float(summary.total) / float(summary.elapsed_sec)) if summary.elapsed_sec > 0 else 0.0
    focus_text = ",".join(focus_names) if focus_names else "(全部类别)"
    providers_text = ",".join(summary.providers) if getattr(summary, "providers", None) else "unknown"
    device_text = "CPU" if getattr(summary, "requested_device", "auto") == "cpu" else "GPU优先"
    batch_text = getattr(summary, "used_batch", None)
    imgsz_text = getattr(summary, "used_imgsz", None)
    input_shape_text = getattr(summary, "input_shape", None)
    output_shape_text = getattr(summary, "output_shape", None)
    t_pre = getattr(summary, "preprocess_sec", None)
    t_inf = getattr(summary, "inference_sec", None)
    t_post = getattr(summary, "postprocess_sec", None)
    t_link = getattr(summary, "hardlink_sec", None)
    drawn = getattr(summary, "drawn", 0)
    txt_written = getattr(summary, "txt_written", 0)
    t_draw = getattr(summary, "draw_sec", 0.0)
    labels_layout = f"{out_display}/<类别>/labels" if out_rel else f"{summary.out_dir}/<类别>/labels"
    images_layout = f"{out_display}/<类别>/images" if out_rel else f"{summary.out_dir}/<类别>/images"
    text = (
        f"{progress_status['text']}\n"
        f"完成：images={summary.total} links={summary.written} hardlink={summary.hardlinked} copy={summary.copied} failed={summary.failed}\n"
        f"推理耗时：{summary.elapsed_sec:.2f}s（{fps:.2f} 张/s）\n"
        f"耗时拆分：pre={t_pre:.2f}s infer={t_inf:.2f}s post={t_post:.2f}s link={t_link:.2f}s draw={t_draw:.2f}s\n"
        f"运行参数：device={device_text} providers={providers_text} cuda={getattr(summary, 'cuda_enabled', False)} conf={float(conf):.2f} batch={batch_text} imgsz={imgsz_text} input_shape={input_shape_text} output_shape={output_shape_text}\n"
        f"模型类型：{model_type}；关注类别：{focus_text}；未命中目录：{unmatched_label}\n"
        f"画框输出：{bool(draw_boxes)} drawn={drawn}\n"
        f"标签 txt：{bool(save_txt)} written={txt_written} dir={labels_layout if save_txt else '(关闭)'}\n"
        f"类别目录结构：images={images_layout}；labels={labels_layout}\n"
        f"输出目录：{out_display}\n"
        f"输出压缩包：{zip_saved_rel or '(未打包)'}\n"
        f"统计：[{stats}]"
    )

    progress_status["text"] = f"推理完成：已处理 {summary.total}/{summary.total} 张，剩余 0 张，推理设备：{device_text}"
    progress(1.0, desc=progress_status["text"])
    yield text, zip_tmp, out_rel, 1.0, 1.0 if do_package and zip_tmp else 0.0


def _output_run_choices() -> List[str]:
    root = IMAGES_DIR / "output"
    if not root.exists():
        return []
    return sorted([p.name for p in root.iterdir() if p.is_dir()])


def package_only(out_rel: str) -> Generator[Tuple[str, Optional[str], float], None, None]:
    _ensure_dirs()
    rel = ensure_relative(out_rel)
    if not rel:
        yield "输出目录必须是相对路径（例如 output/20251225_091307）", None, 0.0
        return
    out_dir = (IMAGES_DIR / rel).resolve()

    pkg_pct = {"value": 0.0}

    def _on_pkg(pkg_info: PackageProgress) -> None:
        if pkg_info.total > 0:
            pkg_pct["value"] = min(max(float(pkg_info.processed) / float(pkg_info.total), 0.0), 1.0)

    # 同步 package_output_dir 会阻塞生成器，改为后台线程 + 轮询 yield 实时进度。
    pkg_result: List[PackageSummary] = []
    pkg_error: List[BaseException] = []

    def _run_pkg() -> None:
        try:
            pkg_result.append(package_output_dir(out_dir, progress_callback=_on_pkg))
        except BaseException as exc:  # noqa: BLE001
            pkg_error.append(exc)

    yield "开始打包...", None, 0.0
    t = threading.Thread(target=_run_pkg, daemon=True, name="yolo-package-only")
    t.start()
    while t.is_alive():
        t.join(timeout=0.2)
        yield f"打包进度：{pkg_pct['value'] * 100:.1f}%", None, pkg_pct["value"]

    if pkg_error:
        logger.exception("打包失败")
        yield f"打包失败: {pkg_error[0]}", None, 0.0
        return

    pkg = pkg_result[0]
    try:
        saved_rel = str(Path(pkg.zip_saved_path).resolve().relative_to(IMAGES_DIR))
    except Exception:  # noqa: BLE001
        saved_rel = pkg.zip_saved_path

    yield f"打包完成：{saved_rel}", pkg.zip_tmp_path, 1.0


def build_app() -> gr.Blocks:
    _ensure_dirs()

    with gr.Blocks(title="YOLO ONNX 推理归档 WebUI") as demo:
        gr.Markdown("### YOLO ONNX 推理归档 WebUI（上传模型/图片/zip → 推理 → 按类别归档）")

        with gr.Tab("上传模型"):
            model_file = gr.File(label="选择 .onnx 模型文件", file_count="single")
            model_overwrite = gr.Checkbox(label="同名覆盖（否则保留原文件）", value=False)
            upload_model_btn = gr.Button("上传模型")
            model_status = gr.Textbox(label="状态", interactive=False)
            model_dropdown = gr.Dropdown(label="当前模型列表", choices=_model_choices())

            upload_model_btn.click(
                upload_model,
                inputs=[model_file, model_overwrite],
                outputs=[model_status, model_dropdown],
            )

        with gr.Tab("上传图片"):
            gr.Markdown(
                "支持直接上传图片，或上传 `.zip` 压缩包（后台自动解压仅保留受支持图片，"
                "完成后会把解压目录自动填入下方“图片目录”）。"
            )
            img_files = gr.File(label="选择图片或 .zip（可多选）", file_count="multiple")
            target_subdir = gr.Textbox(
                label="保存到 images 下的相对目录（可选）",
                placeholder="例如：smoke-00434/images 或 uploads/custom_set",
            )
            img_rename = gr.Checkbox(label="重名时生成新文件名（否则跳过）", value=True)
            upload_imgs_btn = gr.Button("上传图片 / 解压 zip")
            img_status = gr.Textbox(label="状态", interactive=False)
            images_rel_out = gr.Textbox(label="图片目录（相对路径，用于推理）", interactive=False)

            upload_imgs_btn.click(
                upload_images,
                inputs=[img_files, target_subdir, img_rename],
                outputs=[img_status, images_rel_out],
            )

        with gr.Tab("运行推理"):
            with gr.Row():
                model_name = gr.Dropdown(label="选择模型", choices=_model_choices())
                refresh_models_btn = gr.Button("刷新模型列表")
            with gr.Row():
                images_rel = gr.Textbox(
                    label="图片目录（相对 images/ 或宿主机绝对路径）",
                    placeholder="例如：smoke-00434/images 或宿主机绝对路径（需与挂载目录一致）",
                )
                imageset_dropdown = gr.Dropdown(label="快捷选择已有目录（可选）", choices=[], multiselect=False)
                refresh_imageset_btn = gr.Button("刷新快捷目录")
                use_imageset_btn = gr.Button("填入选择")
            infer_progress_bar = gr.Slider(0, 1, value=0, step=0.01, label="推理进度", interactive=False)
            package_progress_bar = gr.Slider(0, 1, value=0, step=0.01, label="打包进度", interactive=False)
            with gr.Row():
                model_type = gr.Radio(
                    label="模型类型",
                    choices=["官方COCO", "自训练"],
                    value="官方COCO",
                )
                focus_coco_classes = gr.CheckboxGroup(
                    label="只关注 COCO 类别（可多选；留空=全部）",
                    choices=COCO80_NAMES,
                    value=["person", "car"],
                    visible=True,
                )
                focus_custom_classes = gr.CheckboxGroup(
                    label="只关注自训练类别（来自同名 .names/.txt/.json；可多选；留空=全部）",
                    choices=[],
                    value=[],
                    visible=False,
                )
            custom_hint = gr.Markdown(value="", visible=False)
            with gr.Row():
                unmatched_label = gr.Textbox(label="未命中目录名", value="no_detection")

            with gr.Row():
                conf = gr.Slider(0.0, 1.0, value=0.25, step=0.01, label="置信度阈值 conf")
                iou = gr.Slider(0.0, 1.0, value=0.45, step=0.01, label="NMS IoU 阈值 iou")
            with gr.Row():
                batch = gr.Slider(1, 64, value=16, step=1, label="batch size")
                imgsz = gr.Number(value=None, label="imgsz（可选，留空自动）", precision=0)
            with gr.Row():
                recursive = gr.Checkbox(label="递归扫描子目录", value=True)
                strict_hardlink = gr.Checkbox(label="必须硬链接（失败即报错）", value=True)
                do_package = gr.Checkbox(label="推理结束后打包 zip（-0 不压缩）并下载", value=False)
            with gr.Row():
                preprocess_workers = gr.Slider(1, 16, value=4, step=1, label="预处理线程数（解码/缩放）")
                prefetch_batches = gr.Slider(0, 8, value=2, step=1, label="预取 batch 数（解码与 GPU 重叠）")
                use_cpu = gr.Checkbox(label="使用 CPU 推理", value=False)
                draw_boxes = gr.Checkbox(label="输出画框图片到 <类别>_画框", value=False)
                save_txt = gr.Checkbox(label="导出 YOLO txt 到 labels/", value=False)

            run_btn = gr.Button("开始推理")
            out_text = gr.Textbox(label="结果", lines=5, interactive=False)
            out_zip = gr.File(label="下载输出 zip（output/<run_id>.zip）", interactive=False)
            out_rel_dir = gr.Textbox(label="输出目录（相对 images/）", interactive=False)

            def _set_imageset_choices():
                return gr.Dropdown(choices=_imageset_choices())

            refresh_models_btn.click(
                lambda: gr.Dropdown(choices=_model_choices()),
                inputs=[],
                outputs=[model_name],
            )
            refresh_imageset_btn.click(_set_imageset_choices, inputs=[], outputs=[imageset_dropdown])
            use_imageset_btn.click(lambda x: x, inputs=[imageset_dropdown], outputs=[images_rel])
            images_rel_out.change(lambda x: x, inputs=[images_rel_out], outputs=[images_rel])

            model_type.change(
                _update_class_controls,
                inputs=[model_name, model_type],
                outputs=[focus_coco_classes, focus_custom_classes, custom_hint],
            )
            model_name.change(
                _update_class_controls,
                inputs=[model_name, model_type],
                outputs=[focus_coco_classes, focus_custom_classes, custom_hint],
            )

            run_btn.click(
                run_job,
                inputs=[
                    model_name,
                    images_rel,
                    model_type,
                    focus_coco_classes,
                    focus_custom_classes,
                    unmatched_label,
                    conf,
                    iou,
                    batch,
                    recursive,
                    imgsz,
                    strict_hardlink,
                    do_package,
                    preprocess_workers,
                    prefetch_batches,
                    draw_boxes,
                    save_txt,
                    use_cpu,
                ],
                outputs=[out_text, out_zip, out_rel_dir, infer_progress_bar, package_progress_bar],
            )

        with gr.Tab("单独打包"):
            with gr.Row():
                out_run = gr.Dropdown(label="选择 output 运行目录（run_id）", choices=[])
                refresh_out_btn = gr.Button("刷新")
            out_rel = gr.Textbox(label="输出目录（相对 images/）", placeholder="例如：output/20251225_091307")
            fill_btn = gr.Button("填入选择")
            pkg_btn = gr.Button("开始打包")
            pkg_status = gr.Textbox(label="状态", interactive=False)
            pkg_zip = gr.File(label="下载 zip（临时文件）", interactive=False)
            pkg_progress_only = gr.Slider(0, 1, value=0, step=0.01, label="打包进度", interactive=False)

            def _set_output_run_choices():
                return gr.Dropdown(choices=_output_run_choices())

            refresh_out_btn.click(_set_output_run_choices, inputs=[], outputs=[out_run])
            fill_btn.click(lambda x: f"output/{x}" if x else "", inputs=[out_run], outputs=[out_rel])
            pkg_btn.click(package_only, inputs=[out_rel], outputs=[pkg_status, pkg_zip, pkg_progress_only])

        with gr.Accordion("运行环境", open=False):
            gr.Markdown(
                f"- `IMAGES_DIR`(容器内): `{IMAGES_DIR}`\n"
                f"- `HOST_IMAGES_DIR`(宿主机侧): `{HOST_IMAGES_DIR}`\n"
                f"- `MODELS_DIR`: `{MODELS_DIR}`\n"
                f"- 模型列表：{', '.join(_model_choices()) or '(空)'}\n"
                f"- 图片目录支持相对 `images/` 或宿主机绝对路径；`.zip` 上传后自动解压回填。"
            )

    return demo


def main() -> None:
    app = build_app()
    if hasattr(app, "queue"):
        app.queue()
    app.launch(server_name="0.0.0.0", server_port=7860)


if __name__ == "__main__":
    main()
