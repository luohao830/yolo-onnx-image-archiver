import asyncio
import threading

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

    async def scenario() -> None:
        queue = bus.subscribe("job:3")
        bus.unsubscribe("job:3", queue)
        assert "job:3" not in bus._subscribers  # noqa: SLF001

    asyncio.run(scenario())


def test_event_bus_publish_from_worker_thread_delivers_to_subscriber() -> None:
    bus = EventBus()

    async def scenario() -> None:
        queue = bus.subscribe("job:thread")

        thread = threading.Thread(
            target=lambda: bus.publish("job:thread", {"event_type": "progress", "written": 1})
        )
        thread.start()
        thread.join(timeout=1.0)

        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert event == {"event_type": "progress", "written": 1}

    asyncio.run(scenario())


def test_event_bus_concurrent_publish_delivers_events() -> None:
    bus = EventBus()

    async def scenario() -> None:
        queue = bus.subscribe("job:concurrent")
        threads = [
            threading.Thread(
                target=lambda offset=offset: [
                    bus.publish("job:concurrent", {"i": offset + index})
                    for index in range(10)
                ]
            )
            for offset in range(0, 50, 10)
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=1.0)

        received = [await asyncio.wait_for(queue.get(), timeout=1.0) for _ in range(50)]
        assert {event["i"] for event in received} == set(range(50))

    asyncio.run(scenario())


def test_event_bus_skips_delivery_after_unsubscribe_before_loop_runs() -> None:
    bus = EventBus()

    async def scenario() -> None:
        queue = bus.subscribe("job:stale")
        thread = threading.Thread(target=lambda: bus.publish("job:stale", {"event_type": "progress"}))
        thread.start()
        thread.join(timeout=1.0)
        bus.unsubscribe("job:stale", queue)

        await asyncio.sleep(0)
        assert queue.empty()

    asyncio.run(scenario())


def test_event_bus_removes_subscriber_when_queue_full() -> None:
    bus = EventBus()

    async def scenario() -> None:
        queue = bus.subscribe("job:4")
        # 填满队列（maxsize=256）。
        for i in range(256):
            bus.publish("job:4", {"i": i})
        # 再发一条应移除慢消费者，不抛错。
        bus.publish("job:4", {"i": 256})
        await asyncio.sleep(0)
        assert "job:4" not in bus._subscribers  # noqa: SLF001
        # 已经排队的数据仍可由持有 queue 的消费方读出。
        first = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert first == {"i": 0}

    asyncio.run(scenario())
