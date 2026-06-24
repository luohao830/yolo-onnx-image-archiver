from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    """数据库模型基类。"""


def build_engine(url: str) -> Engine:
    return create_engine(url, future=True)


def create_all(engine: Engine) -> None:
    import backend.db.models  # noqa: F401

    Base.metadata.create_all(engine)
    _ensure_legacy_columns(engine)


def _ensure_legacy_columns(engine: Engine) -> None:
    """对已存在的旧库补齐后续新增的列，避免全量重建。"""
    inspector = inspect(engine)
    if not inspector.has_table("jobs"):
        return
    existing = {col["name"] for col in inspector.get_columns("jobs")}
    if "summary_json" in existing:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE jobs ADD COLUMN summary_json JSON"))


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
