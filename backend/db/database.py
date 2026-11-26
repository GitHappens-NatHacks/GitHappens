"""SQLite storage for ClearCursor settings, gaze calibration profiles, tremor history, and clinical events."""

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
    override = (
        os.environ.get("CLEARCURSOR_DB_PATH", "").strip()
        or os.environ.get("TRUECURSOR_DB_PATH", "").strip()
    )
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "ClearCursor" / "clearcursor.db"
        if sys.platform.startswith("win"):
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
            return base / "ClearCursor" / "clearcursor.db"
        xdg = Path.home() / ".local" / "share"
        xdg = Path(os.environ.get("XDG_DATA_HOME", xdg))
        return xdg / "ClearCursor" / "clearcursor.db"
    return Path(__file__).resolve().parent / "clearcursor.db"


DEFAULT_DB_PATH = default_user_db_path()

_TREMOR_MIGRATION_COLUMNS: tuple[tuple[str, str], ...] = (
    ("resting_band_pct", "REAL NOT NULL DEFAULT 0.0"),
    ("action_band_pct", "REAL NOT NULL DEFAULT 0.0"),
    ("rms_amplitude_px", "REAL NOT NULL DEFAULT 0.0"),
    ("rms_amplitude_mm", "REAL NOT NULL DEFAULT 0.0"),
    ("click_rescues", "INTEGER NOT NULL DEFAULT 0"),
    ("drags_prevented", "INTEGER NOT NULL DEFAULT 0"),
    ("bounces_blocked", "INTEGER NOT NULL DEFAULT 0"),
    ("preset_name", "TEXT NOT NULL DEFAULT 'moderate'"),
)


class Database:
    """Thread-safe SQLite repository for ClearCursor runtime state and clinician telemetry."""

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
                    simulated INTEGER NOT NULL,
                    resting_band_pct REAL NOT NULL DEFAULT 0.0,
                    action_band_pct REAL NOT NULL DEFAULT 0.0,
                    rms_amplitude_px REAL NOT NULL DEFAULT 0.0,
                    rms_amplitude_mm REAL NOT NULL DEFAULT 0.0,
                    click_rescues INTEGER NOT NULL DEFAULT 0,
                    drags_prevented INTEGER NOT NULL DEFAULT 0,
                    bounces_blocked INTEGER NOT NULL DEFAULT 0,
                    preset_name TEXT NOT NULL DEFAULT 'moderate'
                );

                CREATE INDEX IF NOT EXISTS idx_tremor_history_session_ts
                ON tremor_history (session_id, timestamp DESC);

                CREATE INDEX IF NOT EXISTS idx_tremor_history_sim_ts
                ON tremor_history (simulated, timestamp DESC);

                CREATE TABLE IF NOT EXISTS clinical_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    label TEXT NOT NULL,
                    dosage TEXT NOT NULL DEFAULT '',
                    severity INTEGER,
                    notes TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_clinical_events_ts
                ON clinical_events (timestamp DESC);
                """
            )
            existing_cols = {
                row["name"]
                for row in self._conn.execute("PRAGMA table_info(tremor_history)").fetchall()
            }
            for col_name, col_def in _TREMOR_MIGRATION_COLUMNS:
                if col_name not in existing_cols:
                    self._conn.execute(
                        f"ALTER TABLE tremor_history ADD COLUMN {col_name} {col_def}"
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

    def deactivate_calibration(self, source: str) -> None:
        """Mark all calibration profiles for `source` inactive."""
        with self._lock:
            self._conn.execute(
                "UPDATE calibration_profiles SET is_active = 0 WHERE source = ?",
                (source,),
            )
            self._conn.commit()

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
        resting_band_pct: float = 0.0,
        action_band_pct: float = 0.0,
        rms_amplitude_px: float = 0.0,
        rms_amplitude_mm: float = 0.0,
        click_rescues: int = 0,
        drags_prevented: int = 0,
        bounces_blocked: int = 0,
        preset_name: str = "moderate",
    ) -> int:
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO tremor_history (
                    session_id, timestamp, sample_time, tremor_index,
                    dominant_hz, stability_score, medication_state_estimate,
                    stabilization_active, simulated,
                    resting_band_pct, action_band_pct,
                    rms_amplitude_px, rms_amplitude_mm,
                    click_rescues, drags_prevented, bounces_blocked, preset_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    float(resting_band_pct),
                    float(action_band_pct),
                    float(rms_amplitude_px),
                    float(rms_amplitude_mm),
                    int(click_rescues),
                    int(drags_prevented),
                    int(bounces_blocked),
                    str(preset_name or "moderate"),
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def get_tremor_history(
        self,
        *,
        limit: int = 200,
        session_id: str | None = None,
        include_simulated: bool = True,
    ) -> list[dict[str, Any]]:
        with self._lock:
            sim_clause = "" if include_simulated else " AND simulated = 0"
            if session_id is not None:
                rows = self._conn.execute(
                    f"""
                    SELECT * FROM tremor_history
                    WHERE session_id = ?{sim_clause}
                    ORDER BY id DESC LIMIT ?
                    """,
                    (session_id, max(1, int(limit))),
                ).fetchall()
            else:
                where_clause = "" if include_simulated else "WHERE simulated = 0"
                rows = self._conn.execute(
                    f"""
                    SELECT * FROM tremor_history
                    {where_clause}
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
                    "resting_band_pct": r["resting_band_pct"],
                    "action_band_pct": r["action_band_pct"],
                    "dominant_hz": r["dominant_hz"],
                    "rms_amplitude_px": r["rms_amplitude_px"],
                    "rms_amplitude_mm": r["rms_amplitude_mm"],
                    "stability_score": r["stability_score"],
                    "medication_state_estimate": r["medication_state_estimate"],
                    "stabilization_active": bool(r["stabilization_active"]),
                    "simulated": bool(r["simulated"]),
                    "click_rescues": r["click_rescues"],
                    "drags_prevented": r["drags_prevented"],
                    "bounces_blocked": r["bounces_blocked"],
                    "preset_name": r["preset_name"],
                }
                for r in rows
            ]

    def add_clinical_event(
        self,
        *,
        event_type: str,
        label: str,
        timestamp: float | None = None,
        dosage: str = "",
        severity: int | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        ts = float(time.time() if timestamp is None else timestamp)
        sev = None if severity is None else max(1, min(5, int(severity)))
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO clinical_events (timestamp, event_type, label, dosage, severity, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    str(event_type).strip()[:40],
                    str(label).strip()[:120],
                    str(dosage or "").strip()[:80],
                    sev,
                    str(notes or "").strip()[:400],
                ),
            )
            self._conn.commit()
            event_id = int(cur.lastrowid)
        return {
            "id": event_id,
            "timestamp": ts,
            "event_type": str(event_type).strip()[:40],
            "label": str(label).strip()[:120],
            "dosage": str(dosage or "").strip()[:80],
            "severity": sev,
            "notes": str(notes or "").strip()[:400],
        }

    def list_clinical_events(self, *, days: int = 30, limit: int = 200) -> list[dict[str, Any]]:
        cutoff = time.time() - max(1, int(days)) * 86400.0
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM clinical_events
                WHERE timestamp >= ?
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
                """,
                (cutoff, max(1, int(limit))),
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    "timestamp": r["timestamp"],
                    "event_type": r["event_type"],
                    "label": r["label"],
                    "dosage": r["dosage"],
                    "severity": r["severity"],
                    "notes": r["notes"],
                }
                for r in rows
            ]

    def delete_clinical_event(self, event_id: int) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM clinical_events WHERE id = ?",
                (int(event_id),),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def get_session_summaries(
        self,
        *,
        days: int = 14,
        limit: int = 30,
        include_simulated: bool = False,
    ) -> dict[str, Any]:
        cutoff_ts = time.time() - max(1, int(days)) * 86400.0
        sim_filter = "" if include_simulated else " AND simulated = 0"

        with self._lock:
            sim_count_row = self._conn.execute(
                """
                SELECT COUNT(*) AS cnt FROM tremor_history
                WHERE timestamp >= ? AND simulated = 1
                """,
                (cutoff_ts,),
            ).fetchone()
            simulated_sample_count = int(sim_count_row["cnt"]) if sim_count_row else 0

            session_rows = self._conn.execute(
                f"""
                SELECT
                    session_id,
                    MIN(timestamp) AS started_at,
                    MAX(timestamp) AS ended_at,
                    COUNT(*) AS sample_count,
                    ROUND(AVG(stability_score), 2) AS avg_stability_score,
                    ROUND(AVG(tremor_index), 2) AS avg_tremor_index,
                    ROUND(AVG(resting_band_pct), 2) AS avg_resting_band_pct,
                    ROUND(AVG(action_band_pct), 2) AS avg_action_band_pct,
                    ROUND(AVG(rms_amplitude_px), 2) AS avg_rms_amplitude_px,
                    ROUND(AVG(rms_amplitude_mm), 2) AS avg_rms_amplitude_mm,
                    ROUND(AVG(dominant_hz), 2) AS avg_tremor_hz,
                    MAX(stabilization_active) AS had_stabilization,
                    MAX(click_rescues) AS click_rescues,
                    MAX(drags_prevented) AS drags_prevented,
                    MAX(bounces_blocked) AS bounces_blocked,
                    MIN(simulated) AS simulated_only
                FROM tremor_history
                WHERE timestamp >= ?{sim_filter}
                GROUP BY session_id
                ORDER BY ended_at DESC
                LIMIT ?
                """,
                (cutoff_ts, max(1, int(limit))),
            ).fetchall()

            daily_rows = self._conn.execute(
                f"""
                SELECT
                    date(timestamp, 'unixepoch', 'localtime') AS day,
                    COUNT(*) AS sample_count,
                    COUNT(DISTINCT session_id) AS session_count,
                    ROUND(AVG(stability_score), 2) AS avg_stability_score,
                    ROUND(AVG(tremor_index), 2) AS avg_tremor_index,
                    ROUND(AVG(resting_band_pct), 2) AS avg_resting_band_pct,
                    ROUND(AVG(action_band_pct), 2) AS avg_action_band_pct,
                    ROUND(AVG(rms_amplitude_px), 2) AS avg_rms_amplitude_px,
                    ROUND(AVG(rms_amplitude_mm), 2) AS avg_rms_amplitude_mm,
                    ROUND(AVG(dominant_hz), 2) AS avg_tremor_hz
                FROM tremor_history
                WHERE timestamp >= ?{sim_filter}
                GROUP BY day
                ORDER BY day DESC
                LIMIT ?
                """,
                (cutoff_ts, max(1, int(days))),
            ).fetchall()

            hourly_rows = self._conn.execute(
                f"""
                SELECT
                    CAST(strftime('%H', timestamp, 'unixepoch', 'localtime') AS INTEGER) AS hour_of_day,
                    COUNT(*) AS sample_count,
                    ROUND(AVG(stability_score), 2) AS avg_stability_score,
                    ROUND(AVG(tremor_index), 2) AS avg_tremor_index,
                    ROUND(AVG(resting_band_pct), 2) AS avg_resting_band_pct,
                    ROUND(AVG(action_band_pct), 2) AS avg_action_band_pct,
                    ROUND(AVG(rms_amplitude_mm), 2) AS avg_rms_amplitude_mm
                FROM tremor_history
                WHERE timestamp >= ?{sim_filter}
                GROUP BY hour_of_day
                ORDER BY hour_of_day ASC
                """,
                (cutoff_ts,),
            ).fetchall()

            sessions = [
                {
                    "session_id": r["session_id"],
                    "started_at": r["started_at"],
                    "ended_at": r["ended_at"],
                    "sample_count": r["sample_count"],
                    "avg_stability_score": r["avg_stability_score"],
                    "avg_tremor_index": r["avg_tremor_index"],
                    "avg_resting_band_pct": r["avg_resting_band_pct"] or 0.0,
                    "avg_action_band_pct": r["avg_action_band_pct"] or 0.0,
                    "avg_rms_amplitude_px": r["avg_rms_amplitude_px"] or 0.0,
                    "avg_rms_amplitude_mm": r["avg_rms_amplitude_mm"] or 0.0,
                    "avg_tremor_hz": r["avg_tremor_hz"],
                    "had_stabilization": bool(r["had_stabilization"]),
                    "click_rescues": int(r["click_rescues"] or 0),
                    "drags_prevented": int(r["drags_prevented"] or 0),
                    "bounces_blocked": int(r["bounces_blocked"] or 0),
                    "simulated_only": bool(r["simulated_only"]),
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
                    "avg_resting_band_pct": r["avg_resting_band_pct"] or 0.0,
                    "avg_action_band_pct": r["avg_action_band_pct"] or 0.0,
                    "avg_rms_amplitude_px": r["avg_rms_amplitude_px"] or 0.0,
                    "avg_rms_amplitude_mm": r["avg_rms_amplitude_mm"] or 0.0,
                    "avg_tremor_hz": r["avg_tremor_hz"],
                }
                for r in reversed(daily_rows)
            ]

            hourly_profile = [
                {
                    "hour": int(r["hour_of_day"]),
                    "label": f"{int(r['hour_of_day']):02d}:00",
                    "sample_count": r["sample_count"],
                    "avg_stability_score": r["avg_stability_score"],
                    "avg_tremor_index": r["avg_tremor_index"],
                    "avg_resting_band_pct": r["avg_resting_band_pct"] or 0.0,
                    "avg_action_band_pct": r["avg_action_band_pct"] or 0.0,
                    "avg_rms_amplitude_mm": r["avg_rms_amplitude_mm"] or 0.0,
                }
                for r in hourly_rows
            ]

            total_samples = sum(s["sample_count"] for s in sessions)
            functional_summary = {
                "total_samples": total_samples,
                "total_sessions": len(sessions),
                "total_click_rescues": sum(s["click_rescues"] for s in sessions),
                "total_drags_prevented": sum(s["drags_prevented"] for s in sessions),
                "total_bounces_blocked": sum(s["bounces_blocked"] for s in sessions),
                "avg_rms_amplitude_mm": round(
                    sum(s["avg_rms_amplitude_mm"] for s in sessions) / len(sessions), 2
                )
                if sessions
                else 0.0,
                "avg_resting_band_pct": round(
                    sum(s["avg_resting_band_pct"] for s in sessions) / len(sessions), 2
                )
                if sessions
                else 0.0,
                "avg_action_band_pct": round(
                    sum(s["avg_action_band_pct"] for s in sessions) / len(sessions), 2
                )
                if sessions
                else 0.0,
            }

            return {
                "sessions": sessions,
                "daily_trends": daily_trends,
                "hourly_profile": hourly_profile,
                "functional_summary": functional_summary,
                "simulated_sample_count": simulated_sample_count,
            }
