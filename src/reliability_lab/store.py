from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class RunStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tool_results (
                idempotency_key TEXT PRIMARY KEY,
                output TEXT NOT NULL,
                attempts INTEGER NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS approvals (
                idempotency_key TEXT PRIMARY KEY,
                approved INTEGER NOT NULL
            )
            """
        )

    def result_for(self, key: str) -> tuple[dict[str, Any], int] | None:
        row = self.connection.execute(
            "SELECT output, attempts FROM tool_results WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return (json.loads(row["output"]), row["attempts"]) if row else None

    def save_result(self, key: str, output: dict[str, Any], attempts: int) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO tool_results VALUES (?, ?, ?)",
                (key, json.dumps(output, sort_keys=True), attempts),
            )

    def approve(self, key: str) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO approvals VALUES (?, 1)", (key,)
            )

    def is_approved(self, key: str) -> bool:
        row = self.connection.execute(
            "SELECT approved FROM approvals WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return bool(row and row["approved"])

