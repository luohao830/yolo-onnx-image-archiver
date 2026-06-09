from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from threading import Semaphore


class GpuGate:
    def __init__(self, limit: int) -> None:
        if limit < 1:
            raise ValueError("gpu gate limit must be positive")
        self._sem = Semaphore(limit)

    @contextmanager
    def acquire(self) -> Iterator[None]:
        self._sem.acquire()
        try:
            yield
        finally:
            self._sem.release()
