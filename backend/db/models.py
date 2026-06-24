from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


class JobRecord(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    access_token_hash: Mapped[str] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(String(32))
    model_id: Mapped[int | None] = mapped_column(nullable=True)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="created")
    cancel_requested: Mapped[bool] = mapped_column(Boolean(), default=False)
    input_path: Mapped[str | None] = mapped_column(Text(), nullable=True)
    result_dir: Mapped[str | None] = mapped_column(Text(), nullable=True)
    result_zip_path: Mapped[str | None] = mapped_column(Text(), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class ModelRecord(Base):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    slug: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    onnx_path: Mapped[str] = mapped_column(Text())
    sidecar_path: Mapped[str | None] = mapped_column(Text(), nullable=True)
    model_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean(), default=False)
    visible_in_advanced_mode: Mapped[bool] = mapped_column(Boolean(), default=False)
    is_default_person_model: Mapped[bool] = mapped_column(Boolean(), default=False)


class SystemConfigRecord(Base):
    __tablename__ = "system_configs"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text())


class JobEventRecord(Base):
    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text())
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
