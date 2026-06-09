# 平台内核与任务调度实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在保留现有 `webui/processing.py` 推理能力的前提下，建立可脱离 Gradio 运行的 FastAPI 后端、任务持久化、运行时文件管理和全局调度器。

**架构：** 新建 `backend/` 目录承载 API、数据库、服务和调度器，用 SQLite 保存任务、模型和系统配置。通过适配层调用现有 `webui.processing.run_inference()` 与 `package_output_dir()`，让新的任务处理器复用成熟推理与归档逻辑。

**技术栈：** Python、FastAPI、SQLAlchemy、Pydantic、SQLite、pytest、现有 ONNXRuntime 推理代码。

---

## 文件结构

- 修改：`requirements.txt`，加入 FastAPI、SQLAlchemy、`python-multipart`、`uvicorn`。
- 创建：`backend/__init__.py`，声明后端包。
- 创建：`backend/main.py`，创建 FastAPI 应用并挂载路由。
- 创建：`backend/core/config.py`，读取运行路径、数据库路径和并发配置。
- 创建：`backend/core/db.py`，管理 SQLAlchemy engine 和 session。
- 创建：`backend/db/models.py`，定义 `JobRecord`、`ModelRecord`、`SystemConfigRecord`、`JobEventRecord`。
- 创建：`backend/schemas/jobs.py`，定义用户侧任务请求与响应 schema。
- 创建：`backend/schemas/admin.py`，定义模型和系统配置 schema。
- 创建：`backend/repositories/jobs.py`，封装任务数据访问。
- 创建：`backend/repositories/models.py`，封装模型数据访问。
- 创建：`backend/repositories/system_configs.py`，封装系统配置访问。
- 创建：`backend/services/runtime_paths.py`，生成 `runtime/uploads`、`runtime/jobs`、`runtime/results`、`runtime/tmp` 路径。
- 创建：`backend/services/archive_ingest.py`，处理图片和压缩包接收、解压与安全校验。
- 创建：`backend/services/inference_adapter.py`，桥接 `webui.processing`。
- 创建：`backend/services/job_service.py`，负责任务创建、状态推进和下载授权。
- 创建：`backend/workers/gpu_gate.py`，控制 GPU 推理区间并发。
- 创建：`backend/workers/task_runner.py`，执行单个任务。
- 创建：`backend/workers/scheduler.py`，维护队列和最多 3 个执行槽位。
- 创建：`backend/api/routes/health.py`，健康检查路由。
- 创建：`backend/api/routes/public_jobs.py`，用户侧创建任务、上传、查询、下载信息路由。
- 创建：`tests/backend/test_app_smoke.py`，验证后端应用启动和基础路由。
- 创建：`tests/backend/test_job_repository.py`，验证任务表读写。
- 创建：`tests/backend/test_archive_ingest.py`，验证压缩包安全处理。
- 创建：`tests/backend/test_scheduler.py`，验证执行槽位和 GPU 门控。
- 创建：`tests/backend/test_public_jobs_api.py`，验证用户侧 API。

## 任务 1：搭建 FastAPI 骨架与健康检查

**文件：**
- 修改：`requirements.txt`
- 创建：`backend/__init__.py`
- 创建：`backend/main.py`
- 创建：`backend/core/config.py`
- 创建：`backend/api/routes/health.py`
- 测试：`tests/backend/test_app_smoke.py`

- [ ] **步骤 1：编写失败的应用烟雾测试**

```python
from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_healthz_returns_ok() -> None:
    response = client.get("/api/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_contains_health_route() -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/healthz" in schema["paths"]
```

- [ ] **步骤 2：运行测试验证当前失败**

运行：`pytest tests/backend/test_app_smoke.py -v`

预期：`ModuleNotFoundError: No module named 'backend'`。

- [ ] **步骤 3：编写最小后端骨架**

`requirements.txt` 追加：

```text
fastapi
uvicorn
sqlalchemy
python-multipart
pydantic-settings
```

`backend/main.py`：

```python
from fastapi import FastAPI

from backend.api.routes.health import router as health_router


app = FastAPI(title="yolo-platform")
app.include_router(health_router, prefix="/api")
```

`backend/api/routes/health.py`：

```python
from fastapi import APIRouter


router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **步骤 4：重新运行测试验证通过**

运行：`pytest tests/backend/test_app_smoke.py -v`

预期：2 个测试都 `PASS`。

- [ ] **步骤 5：Commit**

```bash
git add requirements.txt backend tests/backend/test_app_smoke.py
git commit -m "feat: scaffold fastapi backend"
```

## 任务 2：建立数据库模型与仓储层

**文件：**
- 创建：`backend/core/db.py`
- 创建：`backend/db/models.py`
- 创建：`backend/repositories/jobs.py`
- 创建：`backend/repositories/models.py`
- 创建：`backend/repositories/system_configs.py`
- 测试：`tests/backend/test_job_repository.py`

- [ ] **步骤 1：编写失败的任务仓储测试**

```python
from pathlib import Path

from backend.core.db import build_engine, create_all, session_scope
from backend.repositories.jobs import JobRepository


def test_job_repository_persists_status_transitions(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)

    with session_scope(engine) as session:
        repo = JobRepository(session)
        job = repo.create_job(job_code="JOB-001", access_token_hash="hash", mode="person_filter")
        repo.mark_uploaded(job.id, input_path="runtime/uploads/JOB-001/input.zip")
        repo.mark_running(job.id)
        repo.mark_completed(job.id, result_dir="runtime/results/JOB-001", result_zip_path="runtime/results/JOB-001.zip")

        saved = repo.get_by_code("JOB-001")
        assert saved.status == "completed"
        assert saved.result_zip_path.endswith("JOB-001.zip")
```

- [ ] **步骤 2：运行测试验证当前失败**

运行：`pytest tests/backend/test_job_repository.py -v`

预期：提示 `backend.core.db` 或 `JobRepository` 不存在。

- [ ] **步骤 3：实现最小数据库和仓储层**

`backend/core/db.py`：

```python
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


def build_engine(url: str):
    return create_engine(url, future=True)


def create_all(engine) -> None:
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(engine) -> Iterator[Session]:
    session = Session(engine)
    try:
        yield session
        session.commit()
    finally:
        session.close()
```

`backend/db/models.py`：

```python
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


class JobRecord(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    access_token_hash: Mapped[str] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="created")
    input_path: Mapped[str | None] = mapped_column(Text(), nullable=True)
    result_dir: Mapped[str | None] = mapped_column(Text(), nullable=True)
    result_zip_path: Mapped[str | None] = mapped_column(Text(), nullable=True)
```

`backend/repositories/jobs.py`：

```python
from backend.db.models import JobRecord


class JobRepository:
    def __init__(self, session):
        self.session = session

    def create_job(self, *, job_code: str, access_token_hash: str, mode: str) -> JobRecord:
        job = JobRecord(job_code=job_code, access_token_hash=access_token_hash, mode=mode, status="created")
        self.session.add(job)
        self.session.flush()
        return job

    def get_by_code(self, job_code: str) -> JobRecord | None:
        return self.session.query(JobRecord).filter_by(job_code=job_code).one_or_none()
```

- [ ] **步骤 4：补齐状态推进方法并验证通过**

补齐 `mark_uploaded()`、`mark_running()`、`mark_completed()` 后运行：

`pytest tests/backend/test_job_repository.py -v`

预期：测试 `PASS`。

- [ ] **步骤 5：Commit**

```bash
git add backend/core/db.py backend/db/models.py backend/repositories tests/backend/test_job_repository.py
git commit -m "feat: add persistence models and job repository"
```

## 任务 3：建立运行时目录和安全解压流程

**文件：**
- 创建：`backend/services/runtime_paths.py`
- 创建：`backend/services/archive_ingest.py`
- 测试：`tests/backend/test_archive_ingest.py`

- [ ] **步骤 1：编写失败的压缩包安全测试**

```python
import zipfile
from pathlib import Path

import pytest

from backend.services.archive_ingest import extract_upload_archive


def test_extract_upload_archive_blocks_zip_slip(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.jpg", "boom")

    with pytest.raises(ValueError, match="非法压缩包路径"):
        extract_upload_archive(archive, tmp_path / "out")
```

- [ ] **步骤 2：运行测试验证当前失败**

运行：`pytest tests/backend/test_archive_ingest.py -v`

预期：`extract_upload_archive` 不存在。

- [ ] **步骤 3：实现运行时路径和安全解压**

`backend/services/runtime_paths.py`：

```python
from pathlib import Path


class RuntimePaths:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.uploads = root / "uploads"
        self.jobs = root / "jobs"
        self.results = root / "results"
        self.tmp = root / "tmp"

    def ensure(self) -> None:
        for path in (self.root, self.uploads, self.jobs, self.results, self.tmp):
            path.mkdir(parents=True, exist_ok=True)
```

`backend/services/archive_ingest.py`：

```python
import zipfile
from pathlib import Path


def extract_upload_archive(archive_path: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with zipfile.ZipFile(archive_path) as zf:
        for info in zf.infolist():
            target = (out_dir / info.filename).resolve()
            if not str(target).startswith(str(out_dir.resolve())):
                raise ValueError("非法压缩包路径")
            zf.extract(info, out_dir)
            if target.is_file():
                extracted.append(target)
    return extracted
```

- [ ] **步骤 4：增加图片后缀过滤和大小/数量限制后验证通过**

运行：`pytest tests/backend/test_archive_ingest.py -v`

预期：`zip slip` 测试、图片过滤测试、文件计数上限测试全部 `PASS`。

- [ ] **步骤 5：Commit**

```bash
git add backend/services/runtime_paths.py backend/services/archive_ingest.py tests/backend/test_archive_ingest.py
git commit -m "feat: add runtime storage and safe archive ingest"
```

## 任务 4：适配现有推理内核并落地任务执行器

**文件：**
- 创建：`backend/services/inference_adapter.py`
- 创建：`backend/services/job_service.py`
- 创建：`backend/workers/task_runner.py`
- 测试：`tests/backend/test_task_runner.py`

- [ ] **步骤 1：编写失败的任务执行测试**

```python
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.services.runtime_paths import RuntimePaths
from backend.workers.task_runner import TaskRunner


def test_task_runner_marks_completed(monkeypatch, tmp_path: Path) -> None:
    summary = {"out_dir": str(tmp_path / "results"), "total": 2, "written": 2}

    monkeypatch.setattr("backend.services.inference_adapter.run_job_inference", lambda *args, **kwargs: summary)
    monkeypatch.setattr("backend.services.inference_adapter.package_job_output", lambda out_dir: str(tmp_path / "results.zip"))

    job_repo = MagicMock()
    job_repo.get.return_value = SimpleNamespace(
        id=1,
        job_code="JOB-001",
        model_id=10,
        images_dir=str(tmp_path / "images"),
        payload_json={"recursive": True, "batch": 8, "imgsz": None, "conf": 0.25, "iou": 0.45},
    )
    model_repo = MagicMock()
    model_repo.get.return_value = SimpleNamespace(onnx_path=str(tmp_path / "model.onnx"))
    config_repo = MagicMock()
    gpu_gate = MagicMock()
    gpu_gate.acquire.return_value.__enter__.return_value = None
    gpu_gate.acquire.return_value.__exit__.return_value = None

    runner = TaskRunner(
        job_repo=job_repo,
        model_repo=model_repo,
        config_repo=config_repo,
        gpu_gate=gpu_gate,
        runtime_paths=RuntimePaths(tmp_path / "runtime"),
    )
    runner.run(job_id=1)

    job_repo.mark_completed.assert_called_once()
```

- [ ] **步骤 2：运行测试验证当前失败**

运行：`pytest tests/backend/test_task_runner.py -v`

预期：`TaskRunner` 构造或 `run_job_inference` 不存在。

- [ ] **步骤 3：实现推理适配层**

`backend/services/inference_adapter.py`：

```python
from pathlib import Path

from webui.processing import package_output_dir, run_inference


def run_job_inference(*, model_path: Path, images_dir: Path, out_dir: Path, payload: dict) -> dict:
    summary = run_inference(
        model_path=model_path,
        images_dir=images_dir,
        out_dir=out_dir,
        recursive=payload["recursive"],
        batch=payload["batch"],
        imgsz=payload["imgsz"],
        conf=payload["conf"],
        iou=payload["iou"],
        copy_fallback=payload["copy_fallback"],
        preprocess_workers=payload["preprocess_workers"],
        prefetch_batches=payload["prefetch_batches"],
        allowed_class_ids=payload["allowed_class_ids"],
        unmatched_label=payload["unmatched_label"],
        force_class_names=payload["force_class_names"],
        draw_boxes=payload["draw_boxes"],
        save_txt=payload["save_txt"],
        execution_device=payload["execution_device"],
    )
    return summary.__dict__
```

`backend/workers/task_runner.py`：

```python
class TaskRunner:
    def __init__(self, job_repo, model_repo, config_repo, gpu_gate, runtime_paths):
        self.job_repo = job_repo
        self.model_repo = model_repo
        self.config_repo = config_repo
        self.gpu_gate = gpu_gate
        self.runtime_paths = runtime_paths

    def run(self, job_id: int) -> None:
        job = self.job_repo.get(job_id)
        model = self.model_repo.get(job.model_id)
        out_dir = self.runtime_paths.results / job.job_code
        self.job_repo.mark_running(job_id)
        with self.gpu_gate.acquire():
            summary = run_job_inference(
                model_path=Path(model.onnx_path),
                images_dir=Path(job.images_dir),
                out_dir=out_dir,
                payload=job.payload_json,
            )
        zip_path = package_job_output(Path(summary["out_dir"]))
        self.job_repo.mark_completed(job_id, result_dir=summary["out_dir"], result_zip_path=zip_path)
```

- [ ] **步骤 4：补齐失败分支和事件记录后验证通过**

运行：`pytest tests/backend/test_task_runner.py -v`

预期：成功路径、失败路径、打包路径 3 类测试都 `PASS`。

- [ ] **步骤 5：Commit**

```bash
git add backend/services/inference_adapter.py backend/services/job_service.py backend/workers/task_runner.py tests/backend/test_task_runner.py
git commit -m "feat: bridge existing inference core into task runner"
```

## 任务 5：实现调度器与 GPU 门控

**文件：**
- 创建：`backend/workers/gpu_gate.py`
- 创建：`backend/workers/scheduler.py`
- 测试：`tests/backend/test_scheduler.py`

- [ ] **步骤 1：编写失败的并发控制测试**

```python
import threading
import time

from backend.workers.gpu_gate import GpuGate


def test_gpu_gate_only_allows_one_holder() -> None:
    gate = GpuGate(limit=1)
    timeline: list[str] = []

    def worker(name: str) -> None:
        with gate.acquire():
            timeline.append(f"{name}-start")
            time.sleep(0.05)
            timeline.append(f"{name}-end")

    t1 = threading.Thread(target=worker, args=("a",))
    t2 = threading.Thread(target=worker, args=("b",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert timeline in (["a-start", "a-end", "b-start", "b-end"], ["b-start", "b-end", "a-start", "a-end"])
```

- [ ] **步骤 2：运行测试验证当前失败**

运行：`pytest tests/backend/test_scheduler.py -v`

预期：`GpuGate` 或 `Scheduler` 不存在。

- [ ] **步骤 3：实现最小门控和队列调度器**

`backend/workers/gpu_gate.py`：

```python
from contextlib import contextmanager
from threading import Semaphore


class GpuGate:
    def __init__(self, limit: int) -> None:
        self._sem = Semaphore(limit)

    @contextmanager
    def acquire(self):
        self._sem.acquire()
        try:
            yield
        finally:
            self._sem.release()
```

`backend/workers/scheduler.py`：

```python
import queue
import threading


class Scheduler:
    def __init__(self, runner_factory, slots: int) -> None:
        self.runner_factory = runner_factory
        self.slots = slots
        self.queue: "queue.Queue[int]" = queue.Queue()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        for _ in range(self.slots):
            thread = threading.Thread(target=self._loop, daemon=True)
            thread.start()
            self._threads.append(thread)
```

- [ ] **步骤 4：补齐取消、空队列轮询和槽位上限测试后验证通过**

运行：`pytest tests/backend/test_scheduler.py -v`

预期：门控测试、槽位数量测试、取消排队任务测试全部 `PASS`。

- [ ] **步骤 5：Commit**

```bash
git add backend/workers/gpu_gate.py backend/workers/scheduler.py tests/backend/test_scheduler.py
git commit -m "feat: add scheduler and gpu gate"
```

## 任务 6：实现用户侧任务 API

**文件：**
- 创建：`backend/schemas/jobs.py`
- 创建：`backend/api/routes/public_jobs.py`
- 修改：`backend/main.py`
- 测试：`tests/backend/test_public_jobs_api.py`

- [ ] **步骤 1：编写失败的用户侧 API 测试**

```python
from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_create_person_filter_job_returns_receipt() -> None:
    response = client.post("/api/jobs", json={"mode": "person_filter"})
    assert response.status_code == 201
    payload = response.json()
    assert payload["job_code"].startswith("JOB-")
    assert "access_token" in payload


def test_get_job_status_requires_access_token() -> None:
    response = client.get("/api/jobs/JOB-404", params={"access_token": "bad"})
    assert response.status_code in {403, 404}
```

- [ ] **步骤 2：运行测试验证当前失败**

运行：`pytest tests/backend/test_public_jobs_api.py -v`

预期：`/api/jobs` 返回 404。

- [ ] **步骤 3：实现创建任务与查询接口**

`backend/schemas/jobs.py`：

```python
from pydantic import BaseModel, Field


class CreateJobRequest(BaseModel):
    mode: str = Field(pattern="^(person_filter|advanced)$")


class JobReceipt(BaseModel):
    job_code: str
    access_token: str
    status: str
```

`backend/api/routes/public_jobs.py`：

```python
from fastapi import APIRouter, HTTPException

from backend.services.job_service import job_service
from backend.schemas.jobs import CreateJobRequest, JobReceipt


router = APIRouter(prefix="/jobs", tags=["public-jobs"])


@router.post("", response_model=JobReceipt, status_code=201)
def create_job(payload: CreateJobRequest) -> JobReceipt:
    receipt = job_service.create_public_job(payload.mode)
    return JobReceipt(**receipt)


@router.get("/{job_code}")
def get_job(job_code: str, access_token: str):
    job = job_service.get_public_job(job_code, access_token)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job
```

- [ ] **步骤 4：补齐上传接口和下载信息接口后验证通过**

运行：`pytest tests/backend/test_public_jobs_api.py -v`

预期：创建、上传、查询、下载信息 4 类测试全部 `PASS`。

- [ ] **步骤 5：Commit**

```bash
git add backend/schemas/jobs.py backend/api/routes/public_jobs.py backend/main.py tests/backend/test_public_jobs_api.py
git commit -m "feat: expose public job api"
```

## 任务 7：端到端验证和本地启动说明

**文件：**
- 修改：`README.md`
- 验证：`backend/`
- 验证：`tests/backend/`

- [ ] **步骤 1：补充后端本地运行说明**

在 `README.md` 中增加：

````markdown
## Backend Dev

```bash
uvicorn backend.main:app --reload --port 8000
pytest tests/backend -v
```
````

- [ ] **步骤 2：运行后端测试套件**

运行：`pytest tests/backend -v`

预期：全部 `PASS`。

- [ ] **步骤 3：运行后端启动冒烟检查**

运行：`uvicorn backend.main:app --port 8000`

预期：进程正常启动，访问 `/api/healthz` 返回 `{"status":"ok"}`。

- [ ] **步骤 4：Commit**

```bash
git add README.md
git commit -m "docs: document backend development flow"
```
