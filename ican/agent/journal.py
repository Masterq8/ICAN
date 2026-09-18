"""Durable pre-dispatch reservations shared by planning and answer calls."""

import json
import os
from pathlib import Path
from uuid import uuid4

from filelock import FileLock

from .schema import BudgetExhausted


class PaidJournal:
    def __init__(self, path: Path, max_calls=40):
        self.path = Path(path)
        self.max_calls = max_calls
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(str(self.path) + ".lock", timeout=5)

    def _append(self, row):
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def reserve(self, task_id, role, model):
        with self.lock:
            rows = (
                [
                    json.loads(line)
                    for line in self.path.read_text(encoding="utf-8").splitlines()
                ]
                if self.path.exists()
                else []
            )
            if sum(r["event"] == "started" for r in rows) >= self.max_calls:
                raise BudgetExhausted("Cumulative paid-call limit reached")
            call_id = uuid4().hex
            self._append(
                {
                    "event": "started",
                    "call_id": call_id,
                    "task_id": task_id,
                    "role": role,
                    "model": model,
                }
            )
            return call_id

    def finish(self, call_id, *, status, response_model=None, usage=None):
        with self.lock:
            self._append(
                {
                    "event": status,
                    "call_id": call_id,
                    "response_model": response_model,
                    "usage": usage,
                }
            )
