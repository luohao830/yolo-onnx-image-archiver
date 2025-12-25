from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional, Tuple

import gradio as gr

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.logging_utils import get_logger  # noqa: E402
from app.services import (  # noqa: E402
    export_label_zip,
    get_label_counts,
    list_available_labels,
    run_inference_top1,
    sync_images_from_dir,
    preview_images_by_label,
)
from app.settings import DEFAULT_SETTINGS  # noqa: E402
from app.utils import resolve_path  # noqa: E402


logger = get_logger(__name__)


def _list_onnx_models() -> List[str]:
    models_dir = DEFAULT_SETTINGS.models_dir
    if not models_dir.exists():
        return []
    return sorted([p.name for p in models_dir.iterdir() if p.suffix.lower() == ".onnx"])


def _refresh_model_dropdown() -> dict:
    choices = _list_onnx_models()
    value = choices[0] if choices else None
    return gr.Dropdown.update(choices=choices, value=value)


def _refresh_label_dropdown(model_id: str) -> dict:
    choices = list_available_labels(DEFAULT_SETTINGS, model_id=(model_id or "").strip() or None)
    value = choices[0] if choices else None
    return gr.Dropdown.update(choices=choices, value=value)


def _sync_ui(images_dir: str, recursive: bool, batch_size: int, progress=gr.Progress()):
    def cb(_frac: float, desc: str) -> None:
        progress(0.0, desc=desc)

    try:
        msg, rows = sync_images_from_dir(
            DEFAULT_SETTINGS,
            images_dir=images_dir,
            recursive=bool(recursive),
            batch_size=int(batch_size),
            progress=cb,
        )
        return f"### 同步状态\n{msg}", rows
    except Exception as exc:  # noqa: BLE001
        logger.exception("同步失败")
        return f"### 同步状态\n发生错误：{exc}", []


def _infer_ui(
    model_file: str,
    model_id: str,
    confidence: float,
    batch_size: int,
    only_untagged: bool,
    overwrite: bool,
    progress=gr.Progress(),
):
    def cb(frac: float, desc: str) -> None:
        progress(frac, desc=desc)

    try:
        model_path = resolve_path(model_file, DEFAULT_SETTINGS.models_dir)
        msg, rows = run_inference_top1(
            DEFAULT_SETTINGS,
            model_file=str(model_path),
            model_id=(model_id or "").strip() or None,
            confidence=float(confidence),
            batch_size=int(batch_size),
            only_untagged=bool(only_untagged),
            overwrite=bool(overwrite),
            progress=cb,
        )
        return f"### 推理状态\n{msg}", rows
    except Exception as exc:  # noqa: BLE001
        logger.exception("推理失败")
        return f"### 推理状态\n发生错误：{exc}", []


def _counts_ui(model_id: str) -> List[List[object]]:
    try:
        return get_label_counts(DEFAULT_SETTINGS, model_id=(model_id or "").strip() or None)
    except Exception as exc:  # noqa: BLE001
        logger.exception("统计失败")
        return [["error", str(exc)]]


def _preview_ui(label: str, model_id: str, limit: int, offset: int) -> List[Tuple[str, str]]:
    try:
        if not label:
            return []
        return preview_images_by_label(
            DEFAULT_SETTINGS,
            label=label,
            model_id=(model_id or "").strip() or None,
            limit=int(limit),
            offset=int(offset),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("预览失败")
        return []


def _export_ui(
    label: str,
    model_id: str,
    zip_name: str,
    prefer_hardlink: bool,
    progress=gr.Progress(),
) -> Tuple[str, Optional[str]]:
    def cb(frac: float, desc: str) -> None:
        progress(frac, desc=desc)

    try:
        if not label:
            return "### 导出状态\n请先选择标签", None
        msg, zip_path = export_label_zip(
            DEFAULT_SETTINGS,
            label=label,
            model_id=(model_id or "").strip() or None,
            zip_name=(zip_name or "").strip() or None,
            prefer_hardlink=bool(prefer_hardlink),
            progress=cb,
        )
        return f"### 导出状态\n{msg}", zip_path
    except Exception as exc:  # noqa: BLE001
        logger.exception("导出失败")
        return f"### 导出状态\n发生错误：{exc}", None


def _get_theme() -> Optional[gr.Theme]:
    try:
        return gr.themes.Soft(primary_hue="blue", secondary_hue="slate", neutral_hue="slate")
    except Exception:  # noqa: BLE001
        return None


def build_interface() -> gr.Blocks:
    css = """
    .container { max-width: 1180px; margin: 0 auto; }
    #title h1 { margin-bottom: 0.2rem; }
    #title p { margin-top: 0.2rem; color: rgba(0,0,0,0.65); }
    footer { visibility: hidden; }
    """

    with gr.Blocks(
        title="轻量化多模型打标与导出（ONNXRuntime-GPU）",
        theme=_get_theme(),
        css=css,
    ) as demo:
        with gr.Column(elem_classes=["container"]):
            gr.Markdown(
                "# 轻量化多模型打标与导出（ONNXRuntime-GPU）\n"
                "- 图片目录：默认 `/data/images`（宿主机 `./images`）\n"
                "- 模型目录：默认 `/data/models`（宿主机 `./models`，仅 `.onnx`）\n"
                "- 数据库：`/data/state/app.db`（SQLite）\n"
                "- 导出：`/data/exports/*.zip`（支持硬链接 staging，失败回退复制）",
                elem_id="title",
            )

            with gr.Tabs():
                with gr.Tab("1) 同步图片"):
                    images_dir = gr.Textbox(
                        label="图片目录（容器路径）",
                        value=str(DEFAULT_SETTINGS.images_dir),
                    )
                    with gr.Row():
                        recursive = gr.Checkbox(label="递归扫描子目录", value=True)
                        batch_size = gr.Slider(100, 5000, value=1000, step=100, label="写库批大小")
                    sync_btn = gr.Button("同步到库（仅新增）", variant="primary")
                    sync_status = gr.Markdown("### 同步状态\n等待开始。")
                    sync_stats = gr.Dataframe(
                        headers=["指标", "值"],
                        datatype=["str", "number"],
                        interactive=False,
                        label="同步统计",
                    )
                    sync_btn.click(
                        _sync_ui,
                        inputs=[images_dir, recursive, batch_size],
                        outputs=[sync_status, sync_stats],
                    )

                with gr.Tab("2) 推理打标"):
                    with gr.Row():
                        model_file = gr.Dropdown(
                            label="选择模型（.onnx）",
                            choices=_list_onnx_models(),
                            value=None,
                            interactive=True,
                        )
                        refresh_models_btn = gr.Button("刷新", variant="secondary")
                    model_id = gr.Textbox(
                        label="模型 ID（可选，默认取文件名）",
                        value="",
                        placeholder="例如 person_v1 / device_v3",
                    )
                    with gr.Row():
                        confidence = gr.Slider(0.05, 0.9, value=0.25, step=0.05, label="置信度阈值")
                        infer_batch = gr.Slider(1, 128, value=16, step=1, label="Batch Size")
                    with gr.Row():
                        only_untagged = gr.Checkbox(label="仅处理该模型未处理过的图片", value=True)
                        overwrite = gr.Checkbox(label="覆盖该模型旧结果", value=True)
                    infer_btn = gr.Button("开始推理并写入标签", variant="primary")
                    infer_status = gr.Markdown("### 推理状态\n等待开始。")
                    infer_stats = gr.Dataframe(
                        headers=["标签", "数量"],
                        datatype=["str", "number"],
                        interactive=False,
                        label="本次推理统计",
                    )
                    refresh_models_btn.click(_refresh_model_dropdown, outputs=model_file)
                    infer_btn.click(
                        _infer_ui,
                        inputs=[model_file, model_id, confidence, infer_batch, only_untagged, overwrite],
                        outputs=[infer_status, infer_stats],
                    )

                with gr.Tab("3) 浏览与导出"):
                    with gr.Row():
                        filter_model_id = gr.Textbox(
                            label="按模型过滤（可选，留空=聚合）",
                            value="",
                            placeholder="例如 person_v1",
                        )
                        refresh_tags_btn = gr.Button("刷新标签列表", variant="secondary")
                    label = gr.Dropdown(label="标签", choices=[], value=None, interactive=True)
                    counts_btn = gr.Button("刷新统计", variant="secondary")
                    counts = gr.Dataframe(
                        headers=["标签", "数量"],
                        datatype=["str", "number"],
                        interactive=False,
                        label="标签统计（当前过滤）",
                    )

                    with gr.Row():
                        limit = gr.Slider(12, 200, value=60, step=4, label="每页数量")
                        offset = gr.Slider(0, 1000000, value=0, step=60, label="偏移（分页）")
                        preview_btn = gr.Button("预览", variant="primary")
                    gallery = gr.Gallery(label="预览", columns=6, height=520)

                    with gr.Accordion("导出 ZIP", open=True):
                        zip_name = gr.Textbox(
                            label="ZIP 文件名（可选，不含 .zip）",
                            value="",
                            placeholder="留空则自动生成",
                        )
                        prefer_hardlink = gr.Checkbox(label="staging 优先硬链接", value=True)
                        export_btn = gr.Button("导出 ZIP（可下载）", variant="primary")
                        export_status = gr.Markdown("### 导出状态\n等待导出。")
                        export_file = gr.File(label="ZIP 下载", interactive=False)

                    refresh_tags_btn.click(
                        _refresh_label_dropdown,
                        inputs=[filter_model_id],
                        outputs=[label],
                    )
                    counts_btn.click(_counts_ui, inputs=[filter_model_id], outputs=[counts])
                    preview_btn.click(_preview_ui, inputs=[label, filter_model_id, limit, offset], outputs=[gallery])
                    export_btn.click(
                        _export_ui,
                        inputs=[label, filter_model_id, zip_name, prefer_hardlink],
                        outputs=[export_status, export_file],
                    )

                with gr.Tab("说明"):
                    gr.Markdown(
                        "### 类别名来源\n"
                        "- 优先读取 ONNX 的 `custom_metadata_map['names']`\n"
                        "- 否则可在同目录放置 `模型同名.names`（每行一个类别）或 `模型同名.json`\n\n"
                        "### 无检测\n"
                        "- 无检测时写入标签 `no_detection`\n\n"
                        "### 导出 ZIP\n"
                        "- ZIP 内部结构：`<label>/<filename>`\n"
                        "- 若硬链接失败（跨文件系统/权限），会自动回退复制，并在导出状态里显示数量"
                    )

    return demo


if __name__ == "__main__":
    ui = build_interface()
    ui.launch(server_name="0.0.0.0", server_port=7860)

