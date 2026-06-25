from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class _Subscriber:
    queue: asyncio.Queue[Any]
    loop: asyncio.AbstractEventLoop
    active: bool = True


class EventBus:
    """轻量内存事件总线，按 topic 订阅/发布。

    仅适用于单 worker Uvicorn；多 worker 需 Redis pub/sub（本次不引入）。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[str, dict[asyncio.Queue[Any], _Subscriber]] = {}

    def subscribe(self, topic: str) -> asyncio.Queue[Any]:
        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=256)
        loop = asyncio.get_running_loop()
        with self._lock:
            self._subscribers.setdefault(topic, {})[queue] = _Subscriber(queue=queue, loop=loop)
        return queue

    def unsubscribe(self, topic: str, queue: asyncio.Queue[Any]) -> None:
        with self._lock:
            subs = self._subscribers.get(topic)
            if subs and queue in subs:
                subscriber = subs.pop(queue)
                subscriber.active = False
                if not subs:
                    self._subscribers.pop(topic, None)

    def publish(self, topic: str, event: Any) -> None:
        """从任意线程发布事件；订阅者在事件循环中消费。"""
        with self._lock:
            subscribers = list(self._subscribers.get(topic, {}).values())
        if not subscribers:
            return

        for subscriber in subscribers:
            try:
                subscriber.loop.call_soon_threadsafe(self._put_nowait, topic, subscriber, event)
            except RuntimeError:
                logger.warning("event bus loop closed, dropping event for topic=%s", topic)
                self.unsubscribe(topic, subscriber.queue)

    @staticmethod
    def _put_nowait(topic: str, subscriber: _Subscriber, event: Any) -> None:
        if not subscriber.active:
            return
        try:
            subscriber.queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("event bus queue full, dropping event for topic=%s", topic)


# 全局单例（在 main.py 中也可挂到 app.state，这里提供惰性获取入口）。
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _event_bus  # noqa: PLW0603
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
