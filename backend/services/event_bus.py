from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class EventBus:
    """轻量内存事件总线，按 topic 订阅/发布。

    仅适用于单 worker Uvicorn；多 worker 需 Redis pub/sub（本次不引入）。
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[Any]]] = {}

    def subscribe(self, topic: str) -> asyncio.Queue[Any]:
        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=256)
        self._subscribers.setdefault(topic, set()).add(queue)
        return queue

    def unsubscribe(self, topic: str, queue: asyncio.Queue[Any]) -> None:
        subs = self._subscribers.get(topic)
        if subs and queue in subs:
            subs.discard(queue)
            if not subs:
                self._subscribers.pop(topic, None)

    def publish(self, topic: str, event: Any) -> None:
        """从任意线程发布事件；订阅者在事件循环中消费。"""
        subs = self._subscribers.get(topic)
        if not subs:
            return
        for queue in list(subs):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("event bus queue full, dropping event for topic=%s", topic)


# 全局单例（在 main.py 中也可挂到 app.state，这里提供惰性获取入口）。
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _event_bus  # noqa: PLW0603
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
