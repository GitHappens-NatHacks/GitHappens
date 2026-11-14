"""SQLite storage for user settings, gaze calibration profiles, and tremor history."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
import time
from pathlib import Path
from typing import Any

from backend.core.engine.settings import AccessibilitySettings


def default_user_db_path() -> Path:
    """Return a writable per-user SQLite path for packaged desktop runs."""
    override = os.environ.get("TRUECURSOR_DB_PATH", "").strip()
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "TrueCursor" / "truecursor.db"
        if sys.platform.startswith("win"):
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
            return base / "TrueCursor" / "truecursor.db"
        xdg = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        return xdg / "TrueCursor" / "truecursor.db"
    return Path(__file__).resolve().parent / "truecursor.db"


DEFAULT_DB_PATH = default_user_db_path()


class Database:
    """Thread-safe SQLite repository for TrueCursor runtime state."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    payload_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS calibration_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    source TEXT NOT NULL,
                    coef_json TEXT NOT NULL,
                    mean_json TEXT NOT NULL,
                    std_json TEXT NOT NULL,
                    error_px REAL NOT NULL,
                    open_ears_json TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tremor_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    sample_time REAL NOT NULL,
                    tremor_index REAL NOT NULL,
                    dominant_hz REAL,
                    stability_score REAL NOT NULL,
                    medication_state_estimate TEXT NOT NULL,
                    stabilization_active INTEGER NOT NULL,
                    simulated INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_tremor_history_session_ts
                ON tremor_history (session_id, timestamp DESC);
                """
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def load_settings(self) -> AccessibilitySettings:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload_json FROM settings WHERE id = 1"
            ).fetchone()
            if row is None:
                return AccessibilitySettings().validated()
            try:
                data = json.loads(row["payload_json"])
                return AccessibilitySettings.from_dict(data)
            except (ValueError, TypeError):
                return AccessibilitySettings().validated()

    def save_settings(self, settings: AccessibilitySettings) -> AccessibilitySettings:
        validated = settings.validated()
        payload = json.dumps(validated.as_dict(), sort_keys=True)
        now = time.time()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO settings (id, payload_json, updated_at)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (payload, now),
            )
            self._conn.commit()
        return validated

    def save_calibration_profile(
        self,
        *,
        name: str,
        source: str,
        calibration_dict: dict[str, Any],
        error_px: float,
        open_ears: list[float] | None = None,
        activate: bool = True,
    ) -> int:
        now = time.time()
        ears_json = json.dumps(list(open_ears or []))
        with self._lock:
            if activate:
                self._conn.execute(
                    "UPDATE calibration_profiles SET is_active = 0 WHERE source = ?",
                    (source,),
                )
            cur = self._conn.execute(
                """
                INSERT INTO calibration_profiles (
                    name, source, coef_json, mean_json, std_json,
                    error_px, open_ears_json, is_active, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    source,
                    json.dumps(calibration_dict["coef"]),
                    json.dumps(calibration_dict["mean"]),
                    json.dumps(calibration_dict["std"]),
                    float(error_px),
                    ears_json,
                    1 if activate else 0,
                    now,
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def get_active_calibration(self, source: str | None = None) -> dict[str, Any] | None:
        with self._lock:
            if source is not None:
                row = self._conn.execute(
                    """
                    SELECT * FROM calibration_profiles
                    WHERE source = ? AND is_active = 1
                    ORDER BY id DESC LIMIT 1
                    """,
                    (source,),
                ).fetchone()
            else:
                row = self._conn.execute(
                    """
                    SELECT * FROM calibration_profiles
                    WHERE is_active = 1
                    ORDER BY id DESC LIMIT 1
                    """
                ).fetchone()
            return self._row_to_calibration(row) if row is not None else None

    def list_calibration_profiles(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM calibration_profiles
                ORDER BY id DESC LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
            return [self._row_to_calibration(r) for r in rows]

    @staticmethod
    def _row_to_calibration(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "source": row["source"],
            "calibration": {
                "coef": json.loads(row["coef_json"]),
                "mean": json.loads(row["mean_json"]),
                "std": json.loads(row["std_json"]),
            },
            "error_px": row["error_px"],
            "open_ears": json.loads(row["open_ears_json"]),
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
        }

    def record_tremor_sample(
        self,
        *,
        session_id: str,
        timestamp: float,
        sample_time: float,
        tremor_index: float,
        dominant_hz: float | None,
        stability_score: float,
        medication_state_estimate: str,
        stabilization_active: bool,
        simulated: bool,
    ) -> int:
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO tremor_history (
                    session_id, timestamp, sample_time, tremor_index,
                    dominant_hz, stability_score, medication_state_estimate,
                    stabilization_active, simulated
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    float(timestamp),
                    float(sample_time),
                    float(tremor_index),
                    float(dominant_hz) if dominant_hz is not None else None,
                    float(stability_score),
                    medication_state_estimate,
                    1 if stabilization_active else 0,
                    1 if simulated else 0,
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def get_tremor_history(
        self,
        *,
        limit: int = 200,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            if session_id is not None:
                rows = self._conn.execute(
                    """
                    SELECT * FROM tremor_history
                    WHERE session_id = ?
                    ORDER BY id DESC LIMIT ?
                    """,
                    (session_id, max(1, int(limit))),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """
                    SELECT * FROM tremor_history
                    ORDER BY id DESC LIMIT ?
                    """,
                    (max(1, int(limit)),),
                ).fetchall()
            return [
                {
                    "id": r["id"],
                    "session_id": r["session_id"],
                    "timestamp": r["timestamp"],
                    "sample_time": r["sample_time"],
                    "tremor_index": r["tremor_index"],
                    "dominant_hz": r["dominant_hz"],
                    "stability_score": r["stability_score"],
                    "medication_state_estimate": r["medication_state_estimate"],
                    "stabilization_active": bool(r["stabilization_active"]),
                    "simulated": bool(r["simulated"]),
                }
                for r in rows
            ]

    def get_session_summaries(self, *, days: int = 14, limit: int = 30) -> dict[str, Any]:
        with self._lock:
            session_rows = self._conn.execute(
                """
                SELECT
                    session_id,
                    MIN(timestamp) AS started_at,
                    MAX(timestamp) AS ended_at,
                    COUNT(*) AS sample_count,
                    ROUND(AVG(stability_score), 2) AS avg_stability_score,
                    ROUND(AVG(tremor_index), 2) AS avg_tremor_index,
                    ROUND(AVG(dominant_hz), 2) AS avg_tremor_hz,
                    MAX(stabilization_active) AS had_stabilization
                FROM tremor_history
                GROUP BY session_id
                ORDER BY ended_at DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()

            daily_rows = self._conn.execute(
                """
                SELECT
                    date(timestamp, 'unixepoch', 'localtime') AS day,
                    COUNT(*) AS sample_count,
                    COUNT(DISTINCT session_id) AS session_count,
                    ROUND(AVG(stability_score), 2) AS avg_stability_score,
                    ROUND(AVG(tremor_index), 2) AS avg_tremor_index,
                    ROUND(AVG(dominant_hz), 2) AS avg_tremor_hz
                FROM tremor_history
                GROUP BY day
                ORDER BY day DESC
                LIMIT ?
                """,
                (max(1, int(days)),),
            ).fetchall()

            sessions = [
                {
                    "session_id": r["session_id"],
                    "started_at": r["started_at"],
                    "ended_at": r["ended_at"],
                    "sample_count": r["sample_count"],
                    "avg_stability_score": r["avg_stability_score"],
                    "avg_tremor_index": r["avg_tremor_index"],
                    "avg_tremor_hz": r["avg_tremor_hz"],
                    "had_stabilization": bool(r["had_stabilization"]),
                }
                for r in session_rows
            ]

            daily_trends = [
                {
                    "date": r["day"],
                    "sample_count": r["sample_count"],
                    "session_count": r["session_count"],
                    "avg_stability_score": r["avg_stability_score"],
                    "avg_tremor_index": r["avg_tremor_index"],
                    "avg_tremor_hz": r["avg_tremor_hz"],
                }
                for r in reversed(daily_rows)
            ]

            return {"sessions": sessions, "daily_trends": daily_trends}
