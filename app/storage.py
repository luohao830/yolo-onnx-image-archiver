from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .logging_utils import get_logger
from .utils import ensure_dir


logger = get_logger(__name__)


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS images (
  image_id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL UNIQUE,
  added_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS models (
  model_id TEXT PRIMARY KEY,
  onnx_path TEXT NOT NULL,
  imgsz INTEGER NOT NULL,
  class_names_json TEXT,
  added_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  model_id TEXT NOT NULL,
  started_at REAL NOT NULL,
  ended_at REAL,
  conf REAL NOT NULL,
  status TEXT NOT NULL,
  error TEXT,
  FOREIGN KEY(model_id) REFERENCES models(model_id)
);

CREATE TABLE IF NOT EXISTS predictions (
  image_id INTEGER NOT NULL,
  model_id TEXT NOT NULL,
  run_id INTEGER NOT NULL,
  label TEXT NOT NULL,
  confidence REAL,
  created_at REAL NOT NULL,
  PRIMARY KEY(image_id, model_id),
  FOREIGN KEY(image_id) REFERENCES images(image_id),
  FOREIGN KEY(model_id) REFERENCES models(model_id),
  FOREIGN KEY(run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_predictions_label ON predictions(label);
CREATE INDEX IF NOT EXISTS idx_predictions_model ON predictions(model_id);
"""


@dataclass(frozen=True)
class Run:
    run_id: int
    model_id: str
    started_at: float
    ended_at: Optional[float]
    conf: float
    status: str
    error: Optional[str]


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    ensure_dir(db_path.parent)
    conn = _connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
    finally:
        conn.close()


def upsert_images(db_path: Path, paths: Iterable[str]) -> Tuple[int, int]:
    """
    批量插入图片路径，返回 (seen, inserted)。
    """
    now = time.time()
    seen = 0
    inserted = 0
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        for path in paths:
            seen += 1
            try:
                cur.execute(
                    "INSERT INTO images(path, added_at) VALUES(?, ?)",
                    (path, now),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                continue
    finally:
        conn.close()
    return seen, inserted


def count_images(db_path: Path) -> int:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM images").fetchone()
        return int(row["c"])
    finally:
        conn.close()


def upsert_model(
    db_path: Path,
    model_id: str,
    onnx_path: str,
    imgsz: int,
    class_names: Optional[List[str]],
) -> None:
    now = time.time()
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO models(model_id, onnx_path, imgsz, class_names_json, added_at)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(model_id) DO UPDATE SET
              onnx_path=excluded.onnx_path,
              imgsz=excluded.imgsz,
              class_names_json=excluded.class_names_json
            """,
            (
                model_id,
                onnx_path,
                int(imgsz),
                json.dumps(class_names, ensure_ascii=False) if class_names else None,
                now,
            ),
        )
    finally:
        conn.close()


def create_run(db_path: Path, model_id: str, conf: float) -> int:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO runs(model_id, started_at, conf, status) VALUES(?, ?, ?, ?)",
            (model_id, time.time(), float(conf), "running"),
        )
        return int(cur.lastrowid)
    finally:
        conn.close()


def finish_run(db_path: Path, run_id: int, status: str, error: Optional[str] = None) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE runs SET ended_at=?, status=?, error=? WHERE run_id=?",
            (time.time(), status, error, int(run_id)),
        )
    finally:
        conn.close()


def iter_image_paths(db_path: Path) -> Iterable[str]:
    conn = _connect(db_path)
    try:
        for row in conn.execute("SELECT path FROM images ORDER BY image_id ASC"):
            yield str(row["path"])
    finally:
        conn.close()


def iter_image_paths_without_model(db_path: Path, model_id: str) -> Iterable[str]:
    conn = _connect(db_path)
    try:
        sql = """
        SELECT i.path
        FROM images i
        LEFT JOIN predictions p
          ON p.image_id=i.image_id AND p.model_id=?
        WHERE p.image_id IS NULL
        ORDER BY i.image_id ASC
        """
        for row in conn.execute(sql, (model_id,)):
            yield str(row["path"])
    finally:
        conn.close()


def write_predictions_top1(
    db_path: Path,
    run_id: int,
    model_id: str,
    items: Iterable[Tuple[str, str, Optional[float]]],
    overwrite: bool = True,
) -> int:
    """
    写入 top1 结果：items = (image_path, label, confidence)。
    """
    conn = _connect(db_path)
    written = 0
    try:
        cur = conn.cursor()
        for image_path, label, conf in items:
            image_row = cur.execute(
                "SELECT image_id FROM images WHERE path=?",
                (image_path,),
            ).fetchone()
            if image_row is None:
                continue
            image_id = int(image_row["image_id"])
            now = time.time()
            if overwrite:
                cur.execute(
                    """
                    INSERT INTO predictions(image_id, model_id, run_id, label, confidence, created_at)
                    VALUES(?, ?, ?, ?, ?, ?)
                    ON CONFLICT(image_id, model_id) DO UPDATE SET
                      run_id=excluded.run_id,
                      label=excluded.label,
                      confidence=excluded.confidence,
                      created_at=excluded.created_at
                    """,
                    (image_id, model_id, int(run_id), label, conf, now),
                )
            else:
                try:
                    cur.execute(
                        """
                        INSERT INTO predictions(image_id, model_id, run_id, label, confidence, created_at)
                        VALUES(?, ?, ?, ?, ?, ?)
                        """,
                        (image_id, model_id, int(run_id), label, conf, now),
                    )
                except sqlite3.IntegrityError:
                    continue
            written += 1
    finally:
        conn.close()
    return written


def list_labels(db_path: Path, model_id: Optional[str] = None) -> List[str]:
    conn = _connect(db_path)
    try:
        if model_id:
            rows = conn.execute(
                "SELECT DISTINCT label FROM predictions WHERE model_id=? ORDER BY label ASC",
                (model_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT DISTINCT label FROM predictions ORDER BY label ASC"
            ).fetchall()
        return [str(r["label"]) for r in rows]
    finally:
        conn.close()


def label_counts(db_path: Path, model_id: Optional[str] = None) -> List[Tuple[str, int]]:
    conn = _connect(db_path)
    try:
        if model_id:
            rows = conn.execute(
                """
                SELECT label, COUNT(*) AS c
                FROM predictions
                WHERE model_id=?
                GROUP BY label
                ORDER BY c DESC, label ASC
                """,
                (model_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT label, COUNT(*) AS c
                FROM predictions
                GROUP BY label
                ORDER BY c DESC, label ASC
                """
            ).fetchall()
        return [(str(r["label"]), int(r["c"])) for r in rows]
    finally:
        conn.close()


def get_image_paths_by_label(
    db_path: Path,
    label: str,
    model_id: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> List[str]:
    conn = _connect(db_path)
    try:
        if model_id:
            rows = conn.execute(
                """
                SELECT i.path
                FROM predictions p
                JOIN images i ON i.image_id=p.image_id
                WHERE p.label=? AND p.model_id=?
                ORDER BY i.image_id ASC
                LIMIT ? OFFSET ?
                """,
                (label, model_id, int(limit), int(offset)),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT i.path
                FROM predictions p
                JOIN images i ON i.image_id=p.image_id
                WHERE p.label=?
                ORDER BY i.image_id ASC
                LIMIT ? OFFSET ?
                """,
                (label, int(limit), int(offset)),
            ).fetchall()
        return [str(r["path"]) for r in rows]
    finally:
        conn.close()


def list_models(db_path: Path) -> List[Dict[str, object]]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT model_id, onnx_path, imgsz, class_names_json FROM models ORDER BY model_id ASC"
        ).fetchall()
        out: List[Dict[str, object]] = []
        for r in rows:
            out.append(
                {
                    "model_id": str(r["model_id"]),
                    "onnx_path": str(r["onnx_path"]),
                    "imgsz": int(r["imgsz"]),
                    "class_names": json.loads(r["class_names_json"])
                    if r["class_names_json"]
                    else None,
                }
            )
        return out
    finally:
        conn.close()

