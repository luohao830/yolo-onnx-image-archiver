from __future__ import annotations

import asyncio
import json
from typing import Annotated, Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from backend.api.deps import require_admin_sse
from backend.services.event_bus import EventBus
from backend.services.job_presenter import JobPresenter
from backend.services.job_service import JobService, get_job_service


router = APIRouter(tags=["events"])

KEEPALIVE_SECONDS = 30.0


def _sse(data: Any) -> bytes:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


def _event_bus_from_request(request: Request) -> EventBus | None:
    return getattr(request.app.state, "event_bus", None)


async def _stream_events(
    *,
    topic: str,
    history: list[dict[str, Any]],
    bus: EventBus | None,
    request: Request | None = None,
    filter_public: bool = False,
) -> AsyncIterator[bytes]:
    """SSE 事件流：先回放历史，再订阅 EventBus 实时推送。

    注意：订阅发生在历史回放之后，存在一个微小窗口内发生的事件可能丢失。
    当前单 worker 部署下此窗口极短，暂不引入去重机制；多 worker 需引入
    全局回放序列号或 Redis pub/sub 来解决此问题。
    """
    async def _is_disconnected() -> bool:
        if request is None:
            return False
        return await request.is_disconnected()

    # 先回放历史事件。
    for event in history:
        yield _sse(event)

    if bus is None:
        # 无事件总线时退化为纯历史回放 + keepalive。
        while True:
            if await _is_disconnected():
                break
            await asyncio.sleep(KEEPALIVE_SECONDS)
            yield b": keepalive\n\n"
        return

    queue = bus.subscribe(topic)
    try:
        while True:
            if await _is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                if filter_public:
                    event = _filter_event_for_public(event)
                yield _sse(event)
            except asyncio.TimeoutError:
                yield b": keepalive\n\n"
    finally:
        bus.unsubscribe(topic, queue)


def _filter_event_for_public(event: dict[str, Any]) -> dict[str, Any]:
    """对公开 SSE 实时事件过滤掉服务器路径等内部字段。"""
    payload = event.get("payload_json")
    if isinstance(payload, dict):
        event = dict(event)
        event["payload_json"] = JobPresenter.sanitize_event_payload(payload)
    elif payload is not None and not isinstance(payload, dict):
        # 非 dict 类型的 payload（如字符串、列表）不安全，直接替换为空字典。
        event = dict(event)
        event["payload_json"] = {}
    return event


@router.get("/jobs/{job_code}/events")
async def stream_public_job_events(
    job_code: str,
    access_token: str,
    request: Request,
    service: Annotated[JobService, Depends(get_job_service)],
) -> StreamingResponse:
    job = service.get_public_job(job_code, access_token)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    events = job.get("events", [])
    job_id = job.get("id")
    if job_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    bus = _event_bus_from_request(request)
    return StreamingResponse(
        _stream_events(topic=f"job:{job_id}", history=events, bus=bus, request=request, filter_public=True),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/admin/jobs/{job_id}/events")
async def stream_admin_job_events(
    job_id: int,
    request: Request,
    _admin: Annotated[dict[str, Any], Depends(require_admin_sse)],
    service: Annotated[JobService, Depends(get_job_service)],
) -> StreamingResponse:
    try:
        job = service.get_admin_job(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    events = job.get("events", [])
    bus = _event_bus_from_request(request)
    return StreamingResponse(
        _stream_events(topic=f"job:{job_id}", history=events, bus=bus, request=request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
