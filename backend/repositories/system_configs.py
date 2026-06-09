from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from backend.db.models import SystemConfigRecord


class SystemConfigRepository:
    """系统配置仓储。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self) -> Sequence[SystemConfigRecord]:
        return self.session.query(SystemConfigRecord).order_by(SystemConfigRecord.key.asc()).all()

    def get(self, key: str) -> SystemConfigRecord | None:
        return self.session.get(SystemConfigRecord, key)

    def set(self, key: str, value: str) -> SystemConfigRecord:
        record = self.get(key)
        if record is None:
            record = SystemConfigRecord(key=key, value=value)
            self.session.add(record)
        else:
            record.value = value
        self.session.flush()
        return record
