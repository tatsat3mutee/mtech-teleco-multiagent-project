"""
Inference logger — dual SQLite/PostgreSQL backend.

Defaults to SQLite (file: inferences.db). When DATABASE_URL env var is
set (postgresql://user:pass@host/db), uses PostgreSQL instead — suitable
for Neon.tech free tier or any managed Postgres.

Schema and query patterns are identical between backends; only _conn()
differs. All public functions (log_inference, fetch_recent, stats) have
the same signature regardless of backend.

Configuration:
    DATABASE_URL: postgresql://... → PostgreSQL mode
    RAGML_PROJECT_ROOT: override SQLite file location
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DATABASE_URL = os.environ.get("DATABASE_URL", "")
_USE_PG = _DATABASE_URL.startswith("postgresql://") or _DATABASE_URL.startswith("postgres://")

_PROJECT_ROOT = os.environ.get("RAGML_PROJECT_ROOT")
if _PROJECT_ROOT:
    _DB_PATH = Path(_PROJECT_ROOT) / "inferences.db"
else:
    _DB_PATH = Path(__file__).resolve().parents[2] / "inferences.db"

if not _USE_PG:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS inferences (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT    NOT NULL,
    anomaly_id    TEXT,
    anomaly_type  TEXT,
    severity      TEXT,
    root_cause    TEXT,
    confidence    REAL,
    latency_ms    REAL,
    provider      TEXT,
    model         TEXT,
    source        TEXT
);
CREATE INDEX IF NOT EXISTS idx_inferences_ts ON inferences(timestamp);
CREATE INDEX IF NOT EXISTS idx_inferences_type ON inferences(anomaly_type);
"""

_SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS inferences (
    id            SERIAL PRIMARY KEY,
    timestamp     TEXT    NOT NULL,
    anomaly_id    TEXT,
    anomaly_type  TEXT,
    severity      TEXT,
    root_cause    TEXT,
    confidence    REAL,
    latency_ms    REAL,
    provider      TEXT,
    model         TEXT,
    source        TEXT
);
CREATE INDEX IF NOT EXISTS idx_inferences_ts ON inferences(timestamp);
CREATE INDEX IF NOT EXISTS idx_inferences_type ON inferences(anomaly_type);
"""


def _conn():
    """Return a database connection. SQLite by default; PostgreSQL when DATABASE_URL is set."""
    if _USE_PG:
        try:
            import psycopg2
            conn = psycopg2.connect(_DATABASE_URL, connect_timeout=5)
            cur = conn.cursor()
            for stmt in _SCHEMA_PG.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    try:
                        cur.execute(stmt)
                    except Exception:
                        conn.rollback()
            conn.commit()
            cur.close()
            return conn
        except Exception as exc:
            print(f"[inference_log] PostgreSQL connection failed ({exc}), falling back to SQLite")
    # SQLite with WAL mode and extended timeout to prevent "database is locked"
    conn = sqlite3.connect(str(_DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.executescript(_SCHEMA_SQLITE)
    return conn


def log_inference(
    anomaly_id: str,
    anomaly_type: str,
    severity: str,
    root_cause: str,
    confidence: float,
    latency_ms: float,
    source: str = "ui_single",
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    """Append a row. Best-effort — never raises into the UI."""
    try:
        if provider is None or model is None:
            try:
                from config import LLM_PROVIDER, LLM_MODEL
                provider = provider or LLM_PROVIDER
                model = model or LLM_MODEL
            except Exception:
                provider = provider or "unknown"
                model = model or "unknown"
        with _conn() as c:
            c.execute(
                """INSERT INTO inferences
                   (timestamp, anomaly_id, anomaly_type, severity, root_cause,
                    confidence, latency_ms, provider, model, source)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    str(anomaly_id),
                    str(anomaly_type),
                    str(severity),
                    str(root_cause)[:2000],
                    float(confidence) if confidence is not None else None,
                    float(latency_ms) if latency_ms is not None else None,
                    provider,
                    model,
                    source,
                ),
            )
    except Exception as e:
        # Logging must never break inference
        print(f"[inference_log] write failed: {e}")


def fetch_recent(limit: int = 50):
    """Return most-recent N rows as list of dicts (for the dashboard view)."""
    try:
        with _conn() as c:
            c.row_factory = sqlite3.Row
            rows = c.execute(
                "SELECT * FROM inferences ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        print(f"[inference_log] read failed: {e}")
        return []


def stats():
    """Aggregate stats for the dashboard."""
    try:
        with _conn() as c:
            total = c.execute("SELECT COUNT(*) FROM inferences").fetchone()[0]
            avg_lat = c.execute("SELECT AVG(latency_ms) FROM inferences").fetchone()[0]
            by_type = c.execute(
                "SELECT anomaly_type, COUNT(*) AS n, AVG(latency_ms) AS lat "
                "FROM inferences GROUP BY anomaly_type ORDER BY n DESC"
            ).fetchall()
            return {
                "total": total,
                "avg_latency_ms": avg_lat,
                "by_type": [
                    {"type": r[0], "count": r[1], "avg_latency_ms": r[2]} for r in by_type
                ],
            }
    except Exception as e:
        print(f"[inference_log] stats failed: {e}")
        return {"total": 0, "avg_latency_ms": None, "by_type": []}
