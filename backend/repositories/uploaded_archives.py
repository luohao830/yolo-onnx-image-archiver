from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.core.db import session_scope
from backend.db.models import UploadedArchiveRecord


class UploadedArchiveRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    @classmethod
    def create_for_engine(
        cls,
        engine: Engine,
        *,
        content_sha256: str,
        original_filename: str,
        archive_path: str,
        extracted_path: str,
        size_bytes: int,
        image_count: int,
    ) -> UploadedArchiveRecord:
        with session_scope(engine) as session:
            archive = cls(session).create(
                content_sha256=content_sha256,
                original_filename=original_filename,
                archive_path=archive_path,
                extracted_path=extracted_path,
                size_bytes=size_bytes,
                image_count=image_count,
            )
            session.expunge(archive)
            return archive

    def create(
        self,
        *,
        content_sha256: str,
        original_filename: str,
        archive_path: str,
        extracted_path: str,
        size_bytes: int,
        image_count: int,
    ) -> UploadedArchiveRecord:
        archive = UploadedArchiveRecord(
            content_sha256=content_sha256,
            original_filename=original_filename,
            archive_path=archive_path,
            extracted_path=extracted_path,
            size_bytes=size_bytes,
            image_count=image_count,
        )
        self.session.add(archive)
        self.session.flush()
        return archive

    def get(self, archive_id: int) -> UploadedArchiveRecord | None:
        return self.session.get(UploadedArchiveRecord, archive_id)

    def get_by_sha256(self, content_sha256: str) -> UploadedArchiveRecord | None:
        return self.session.query(UploadedArchiveRecord).filter_by(content_sha256=content_sha256).one_or_none()

    def list_archives(self) -> list[UploadedArchiveRecord]:
        return self.session.query(UploadedArchiveRecord).order_by(UploadedArchiveRecord.id.asc()).all()

    def delete_many(self, ids: Iterable[int]) -> list[UploadedArchiveRecord]:
        archives = [
            archive
            for archive_id in ids
            if (archive := self.get(int(archive_id))) is not None
        ]
        for archive in archives:
            self.session.delete(archive)
        self.session.flush()
        return archives
