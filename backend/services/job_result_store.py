from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.services import inference_adapter
from backend.services.job_presenter import JobPresenter


class JobResultStore:
    """统一结果 zip / detections / 图片的安全路径解析与读取。

    路由和页面不应感知 _detections.json 等内部文件名。
    """

    @classmethod
    def resolve_result_zip(cls, job: Any) -> Path:
        """校验任务状态并从 record 中解析结果 zip 路径。"""
        return JobPresenter.resolve_result_zip(job)

    @classmethod
    def resolve_result_dir(cls, job: Any) -> Path | None:
        return JobPresenter.resolve_result_dir(job)

    @classmethod
    def read_detections(cls, result_dir: Path) -> dict[str, Any] | None:
        """从 result_dir 读取 _detections.json，内部文件名对外不可见。"""
        return inference_adapter.read_detections_json(result_dir)

    @classmethod
    def resolve_image(cls, result_dir: Path, rel_path: str) -> Path | None:
        """安全解析 result_dir 下的相对图片路径。"""
        return JobPresenter.safe_resolve_within(result_dir, rel_path)
