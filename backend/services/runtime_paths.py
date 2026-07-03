from __future__ import annotations

from pathlib import Path


class RuntimePaths:
    """集中管理运行时目录结构。"""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.uploads = root / "uploads"
        self.jobs = root / "jobs"
        self.results = root / "results"
        self.tmp = root / "tmp"

    def ensure(self) -> None:
        """确保所有运行时目录存在，不存在则递归创建。"""
        for path in (self.root, self.uploads, self.jobs, self.results, self.tmp):
            path.mkdir(parents=True, exist_ok=True)
