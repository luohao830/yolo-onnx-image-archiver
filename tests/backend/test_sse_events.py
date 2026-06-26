import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.api.routes.public_events import _stream_events, stream_public_job_events
from backend.core.db import build_engine, create_all, session_scope
from backend.core.job_events_auth import JobEventsTokenService
from backend.db.models import ModelRecord
from backend.main import app
from starlette.requests import Request
from backend.repositories.jobs import JobRepository
from backend.services.event_bus import EventBus, get_event_bus
from backend.services.job_service import JobService, get_job_service
from backend.services.runtime_paths import RuntimePaths

from backend.api.routes.public_jobs import get_job


def _seed(tmp_path: Path) -> tuple[JobService, str, str, int]:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    runtime_paths = RuntimePaths(tmp_path / "runtime")
    service = JobService(engine, runtime_paths=runtime_paths)

    receipt = service.create_public_job("person_filter")
    job_code = receipt["job_code"]
    access_token = receipt["access_token"]
    with session_scope(engine) as session:
        model = ModelRecord(onnx_path=str(tmp_path / "model.onnx"))
        session.add(model)
        session.flush()
        repo = JobRepository(session)
        job = repo.get_by_code(job_code)
        assert job is not None
        repo.mark_uploaded(job.id, input_path=str(tmp_path / "images"), model_id=model.id)
        repo.record_event(
            job.id,
            event_type="running",
            message="任务开始执行",
            payload_json={"stage": "running", "total": 4, "written": 1},
        )
        job_id = job.id
    return service, job_code, access_token, job_id


def test_stream_events_replays_history(tmp_path: Path) -> None:
    service, job_code, access_token, job_id = _seed(tmp_path)

    async def scenario() -> bytes:
        bus = EventBus()
        gen = _stream_events(
            topic=f"job:{job_id}",
            history=[{"id": 1, "event_type": "running", "message": "任务开始执行", "payload_json": {}}],
            bus=bus,
        )
        # 仅取首块（历史回放），然后取消生成器。
        try:
            first = await asyncio.wait_for(gen.__anext__(), timeout=1.0)
        finally:
            await gen.aclose()
        return first

    chunk = asyncio.run(scenario())
    assert b"\xe4\xbb\xbb\xe5\x8a\xa1\xe5\xbc\x80\xe5\xa7\x8b\xe6\x89\xa7\xe8\xa1\x8c" in chunk  # "任务开始执行"


def test_stream_events_streams_published_event(tmp_path: Path) -> None:
    _service, _code, _token, job_id = _seed(tmp_path)

    async def scenario() -> bytes:
        bus = EventBus()
        gen = _stream_events(topic=f"job:{job_id}", history=[], bus=bus)
        # 启动消费任务，再发布一条事件。
        consume_task = asyncio.create_task(_collect_first(gen))
        await asyncio.sleep(0.05)
        bus.publish(f"job:{job_id}", {"event_type": "completed", "message": "done"})
        result = await asyncio.wait_for(consume_task, timeout=2.0)
        await gen.aclose()
        return result

    async def _collect_first(gen) -> bytes:
        async for chunk in gen:
            if b"completed" in chunk:
                return chunk
        raise AssertionError("未收到事件")

    chunk = asyncio.run(scenario())
    assert b"completed" in chunk



def test_stream_public_job_events_requires_short_lived_token(tmp_path: Path) -> None:
    service, job_code, _access_token, job_id = _seed(tmp_path)
    token_service = JobEventsTokenService("test-secret")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/jobs/JOB/events",
            "headers": [],
            "app": app,
            "client": ("127.0.0.1", 12345),
        }
    )

    with pytest.raises(HTTPException) as missing_token:
        asyncio.run(
            stream_public_job_events(
                job_code,
                request,
                service=service,
                token_service=token_service,
                events_token=None,
            )
        )
    assert missing_token.value.status_code == 401

    response = asyncio.run(
        stream_public_job_events(
            job_code,
            request,
            service=service,
            token_service=token_service,
            events_token=token_service.issue(job_id),
        )
    )
    assert response.media_type == "text/event-stream"


def test_get_public_job_status_includes_summary_field(tmp_path: Path) -> None:
    service, job_code, access_token, _job_id = _seed(tmp_path)
    payload = get_job(job_code, access_token, service=service)
    # summary 字段应存在（未完成时为 None）。
    assert hasattr(payload, "summary")
    assert payload.summary is None


def test_openapi_contains_event_routes() -> None:
    schema = app.openapi()
    assert "/api/jobs/{job_code}/events" in schema["paths"]
    assert "/api/admin/jobs/{job_id}/events" in schema["paths"]


def test_sse_publishes_event_to_subscriber() -> None:
    bus = get_event_bus()

    async def scenario() -> None:
        queue = bus.subscribe("job:99")
        bus.publish("job:99", {"event_type": "completed", "message": "done"})
        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert event["event_type"] == "completed"
        bus.unsubscribe("job:99", queue)

    asyncio.run(scenario())
