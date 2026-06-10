from __future__ import annotations

from collections.abc import Sequence

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

    def list_models(self) -> Sequence[ModelRecord]:
        return self.session.query(ModelRecord).order_by(ModelRecord.id.asc()).all()

    def get_default_person_model(self) -> ModelRecord | None:
        return (
            self.session.query(ModelRecord)
            .filter_by(
                enabled=True,
                is_default_person_model=True,
                model_kind="person_detector",
            )
            .order_by(ModelRecord.id.asc())
            .first()
        )

    def create_model(
        self,
        *,
        name: str,
        slug: str,
        onnx_path: str,
        sidecar_path: str | None,
        model_kind: str,
    ) -> ModelRecord:
        model = ModelRecord(
            name=name,
            slug=slug,
            onnx_path=onnx_path,
            sidecar_path=sidecar_path,
            model_kind=model_kind,
            enabled=False,
            visible_in_advanced_mode=False,
            is_default_person_model=False,
        )
        self.session.add(model)
        self.session.flush()
        return model

    def clear_default_person_model(self) -> None:
        self.session.query(ModelRecord).filter_by(is_default_person_model=True).update(
            {"is_default_person_model": False},
        )
        self.session.flush()

    def update_publish_state(
        self,
        model_id: int,
        *,
        enabled: bool,
        visible_in_advanced_mode: bool,
        is_default_person_model: bool,
    ) -> ModelRecord:
        model = self.get(model_id)
        model.enabled = enabled
        model.visible_in_advanced_mode = visible_in_advanced_mode
        model.is_default_person_model = is_default_person_model
        self.session.flush()
        return model
