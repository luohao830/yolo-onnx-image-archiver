import asyncio

import pytest

from backend.services.event_bus import EventBus


def test_event_bus_publish_delivers_to_subscriber() -> None:
    bus = EventBus()

    async def scenario() -> None:
        queue = bus.subscribe("job:1")
        bus.publish("job:1", {"event_type": "running", "message": "hello"})
        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert event == {"event_type": "running", "message": "hello"}

    asyncio.run(scenario())


def test_event_bus_publish_without_subscribers_is_noop() -> None:
    bus = EventBus()
    bus.publish("job:2", {"event_type": "running"})  # 不应抛错


def test_event_bus_unsubscribe_removes_queue() -> None:
    bus = EventBus()
    queue = bus.subscribe("job:3")
    bus.unsubscribe("job:3", queue)
    assert "job:3" not in bus._subscribers  # noqa: SLF001


def test_event_bus_drops_when_queue_full() -> None:
    bus = EventBus()

    async def scenario() -> None:
        queue = bus.subscribe("job:4")
        # 填满队列（maxsize=256）。
        for i in range(256):
            bus.publish("job:4", {"i": i})
        # 再发一条应被丢弃，不抛错。
        bus.publish("job:4", {"i": 256})
        # 取出几条确认仍可消费。
        first = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert first == {"i": 0}

    asyncio.run(scenario())
