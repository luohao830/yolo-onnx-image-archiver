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
    filter_public: bool = False,
) -> AsyncIterator[bytes]:
    # 先回放历史事件。
    for event in history:
        yield _sse(event)

    if bus is None:
        # 无事件总线时退化为纯历史回放 + keepalive。
        while True:
            await asyncio.sleep(KEEPALIVE_SECONDS)
            yield b": keepalive\n\n"
        return

    queue = bus.subscribe(topic)
    try:
        while True:
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
    if "payload_json" in event and isinstance(event["payload_json"], dict):
        event = dict(event)
        event["payload_json"] = JobPresenter.sanitize_event_payload(event["payload_json"])
    return event


@router.get("/jobs/{job_code}/events")
async def stream_public_job_events(
    job_code: str,
    access_token: str,
    request: Request,
    service: Annotated[JobService, Depends(get_job_service)],
) -> StreamingResponse:
    job_id = service.get_public_job_id(job_code, access_token)
    if job_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    job = service.get_public_job(job_code, access_token)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    events = job.get("events", [])
    bus = _event_bus_from_request(request)
    return StreamingResponse(
        _stream_events(topic=f"job:{job_id}", history=events, bus=bus, filter_public=True),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/admin/jobs/{job_id}/events")
async def stream_admin_job_events(
    job_id: int,
    request: Request,
    admin: Annotated[dict[str, Any], Depends(require_admin_sse)],
    service: Annotated[JobService, Depends(get_job_service)],
) -> StreamingResponse:
    del admin
    try:
        job = service.get_admin_job(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    events = job.get("events", [])
    bus = _event_bus_from_request(request)
    return StreamingResponse(
        _stream_events(topic=f"job:{job_id}", history=events, bus=bus),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
