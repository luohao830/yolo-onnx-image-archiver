from __future__ import annotations

from sqlalchemy.orm import Session

from backend.db.models import ModelRecord


class ModelRepository:
    """模型仓储最小实现。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, model_id: int) -> ModelRecord:
        model = self.session.get(ModelRecord, model_id)
        if model is None:
            raise LookupError(f"model not found: {model_id}")
        return model
