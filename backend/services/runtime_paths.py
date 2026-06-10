from __future__ import annotations

from pathlib import Path


class RuntimePaths:
    """集中管理运行时目录结构。"""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.uploads = root / "uploads"
        self.upload_archives = self.uploads / "archives"
        self.jobs = root / "jobs"
        self.results = root / "results"
        self.tmp = root / "tmp"

    def ensure(self) -> None:
        for path in (self.root, self.uploads, self.upload_archives, self.jobs, self.results, self.tmp):
            path.mkdir(parents=True, exist_ok=True)
