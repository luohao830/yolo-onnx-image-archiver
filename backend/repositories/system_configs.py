from __future__ import annotations

from sqlalchemy.orm import Session


class SystemConfigRepository:
    """系统配置仓储占位，后续任务再补充具体行为。"""

    def __init__(self, session: Session) -> None:
        self.session = session
