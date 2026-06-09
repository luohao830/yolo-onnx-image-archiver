from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String, Text
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
    input_path: Mapped[str | None] = mapped_column(Text(), nullable=True)
    result_dir: Mapped[str | None] = mapped_column(Text(), nullable=True)
    result_zip_path: Mapped[str | None] = mapped_column(Text(), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)


class ModelRecord(Base):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(primary_key=True)
    onnx_path: Mapped[str] = mapped_column(Text())
