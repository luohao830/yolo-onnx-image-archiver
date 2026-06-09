from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


class JobRecord(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    access_token_hash: Mapped[str] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="created")
    input_path: Mapped[str | None] = mapped_column(Text(), nullable=True)
    result_dir: Mapped[str | None] = mapped_column(Text(), nullable=True)
    result_zip_path: Mapped[str | None] = mapped_column(Text(), nullable=True)
