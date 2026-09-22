"""Append-only, local research-record persistence."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from filelock import FileLock

from ican.agent.schema import ToolInputError

from .schema import ResearchRecord


class ResearchStore:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(str(self.directory / ".research.lock"), timeout=5)

    @staticmethod
    def _record_id(value: UUID | str) -> UUID:
        try:
            return UUID(str(value))
        except (TypeError, ValueError) as error:
            raise ToolInputError("Research record ID must be a UUID") from error

    def _path(self, value: UUID | str) -> Path:
        return self.directory / f"{self._record_id(value)}.json"

    def append(self, record: ResearchRecord) -> ResearchRecord:
        path = self._path(record.record_id)
        with self.lock:
            try:
                with path.open("x", encoding="utf-8", newline="\n") as stream:
                    stream.write(record.model_dump_json(indent=2))
                    stream.write("\n")
            except FileExistsError as error:
                raise ToolInputError("Research record ID already exists") from error
        return record

    def load(self, value: UUID | str) -> ResearchRecord:
        path = self._path(value)
        try:
            return ResearchRecord.model_validate(
                json.loads(path.read_text(encoding="utf-8"))
            )
        except FileNotFoundError as error:
            raise ToolInputError("Research record is absent") from error
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise ToolInputError("Research record is invalid") from error

    def latest_for_subject(self, subject_source_id: str, record_type: str):
        latest = None
        for path in self.directory.glob("*.json"):
            record = self.load(path.stem)
            if (
                record.subject_source_id == subject_source_id
                and record.record_type == record_type
                and (
                    latest is None
                    or (record.created_at, str(record.record_id))
                    > (latest.created_at, str(latest.record_id))
                )
            ):
                latest = record
        return latest

    def latest_for_card(self, subject_source_id: str, record_type: str, card_id):
        latest = None
        for path in self.directory.glob("*.json"):
            record = self.load(path.stem)
            if (
                record.subject_source_id == subject_source_id
                and record.record_type == record_type
                and record.card_id == card_id
                and (
                    latest is None
                    or (record.created_at, str(record.record_id))
                    > (latest.created_at, str(latest.record_id))
                )
            ):
                latest = record
        return latest
