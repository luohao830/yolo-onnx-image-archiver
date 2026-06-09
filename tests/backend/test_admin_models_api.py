from __future__ import annotations

from pathlib import Path

from backend.api.routes.admin_configs import UpdateConcurrencyRequest, list_configs, update_concurrency
from backend.api.routes.admin_models import (
    CreateModelRequest,
    PublishModelRequest,
    create_model,
    publish_model,
)
from backend.core.db import build_engine, create_all, session_scope
from backend.db.models import ModelRecord, SystemConfigRecord
from backend.main import app
from backend.services.config_service import ConfigService
from backend.services.model_service import ModelService


ADMIN_CLAIMS = {"role": "admin"}


def test_admin_can_create_model_record(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = ModelService(engine)

    response = create_model(
        CreateModelRequest(
            name="helmet-person-v1",
            slug="helmet-person-v1",
            model_kind="person_detector",
            onnx_path="models/helmet-person-v1.onnx",
        ),
        admin=ADMIN_CLAIMS,
        service=service,
    )

    assert response.name == "helmet-person-v1"
    assert response.slug == "helmet-person-v1"
    assert response.enabled is False
    assert response.visible_in_advanced_mode is False
    assert response.is_default_person_model is False

    with session_scope(engine) as session:
        saved = session.query(ModelRecord).filter_by(slug="helmet-person-v1").one()
        assert saved.model_kind == "person_detector"
        assert saved.onnx_path == "models/helmet-person-v1.onnx"


def test_admin_can_publish_model_and_switch_default_person_model(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = ModelService(engine)

    first = create_model(
        CreateModelRequest(
            name="helmet-person-v1",
            slug="helmet-person-v1",
            model_kind="person_detector",
            onnx_path="models/helmet-person-v1.onnx",
        ),
        admin=ADMIN_CLAIMS,
        service=service,
    )
    second = create_model(
        CreateModelRequest(
            name="helmet-person-v2",
            slug="helmet-person-v2",
            model_kind="person_detector",
            onnx_path="models/helmet-person-v2.onnx",
        ),
        admin=ADMIN_CLAIMS,
        service=service,
    )

    first_published = publish_model(
        first.id,
        PublishModelRequest(
            enabled=True,
            visible_in_advanced_mode=True,
            is_default_person_model=True,
        ),
        admin=ADMIN_CLAIMS,
        service=service,
    )
    second_published = publish_model(
        second.id,
        PublishModelRequest(
            enabled=True,
            visible_in_advanced_mode=True,
            is_default_person_model=True,
        ),
        admin=ADMIN_CLAIMS,
        service=service,
    )

    assert first_published.is_default_person_model is True
    assert second_published.is_default_person_model is True

    with session_scope(engine) as session:
        first_saved = session.get(ModelRecord, first.id)
        second_saved = session.get(ModelRecord, second.id)

        assert first_saved is not None
        assert second_saved is not None
        assert first_saved.is_default_person_model is False
        assert second_saved.is_default_person_model is True
        assert second_saved.enabled is True
        assert second_saved.visible_in_advanced_mode is True


def test_admin_can_list_and_update_concurrency_configs(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = ConfigService(engine)

    defaults = list_configs(admin=ADMIN_CLAIMS, service=service)

    assert defaults.task_slots == 3
    assert defaults.gpu_slots == 1

    updated = update_concurrency(
        UpdateConcurrencyRequest(task_slots=2, gpu_slots=1),
        admin=ADMIN_CLAIMS,
        service=service,
    )

    assert updated.task_slots == 2
    assert updated.gpu_slots == 1

    with session_scope(engine) as session:
        configs = session.query(SystemConfigRecord).all()
        assert {(item.key, item.value) for item in configs} == {
            ("gpu_slots", "1"),
            ("task_slots", "2"),
        }


def test_openapi_contains_admin_model_and_config_routes() -> None:
    schema = app.openapi()

    assert "/api/admin/models" in schema["paths"]
    assert "post" in schema["paths"]["/api/admin/models"]
    assert "get" in schema["paths"]["/api/admin/models"]
    assert "/api/admin/models/{model_id}/publish" in schema["paths"]
    assert "patch" in schema["paths"]["/api/admin/models/{model_id}/publish"]
    assert "/api/admin/configs" in schema["paths"]
    assert "get" in schema["paths"]["/api/admin/configs"]
    assert "/api/admin/configs/concurrency" in schema["paths"]
    assert "put" in schema["paths"]["/api/admin/configs/concurrency"]
