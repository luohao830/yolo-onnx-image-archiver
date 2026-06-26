from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, exc, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """数据库模型基类。"""


def build_engine(url: str) -> Engine:
    return create_engine(url, future=True)


def create_all(engine: Engine) -> None:
    import backend.db.models  # noqa: F401

    Base.metadata.create_all(engine)
    _ensure_legacy_columns(engine)


def _ensure_legacy_columns(engine: Engine) -> None:
    """对已存在的旧库补齐后续新增的列，避免全量重建。

    每条列单独检查并单独 try/except，兼顾并发启动（多 worker 同时 ALTER）
    与未来新增列的扩展性。
    """
    inspector = inspect(engine)
    if not inspector.has_table("jobs"):
        return
    existing = {col["name"] for col in inspector.get_columns("jobs")}
    if "summary_json" not in existing:
        try:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN summary_json JSON"))
        except (exc.OperationalError, exc.ProgrammingError) as err:
            # 并发启动时另一个 worker 可能已添加该列（SQLite 报 "duplicate column"）。
            if _is_duplicate_column_error(err):
                pass
            else:
                logger.exception("Failed to add summary_json column")
                raise
        except Exception:
            logger.exception("Failed to add summary_json column")
            raise


def _is_duplicate_column_error(error: Exception) -> bool:
    message = str(error).lower()
    return "duplicate column" in message or "already exists" in message


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
