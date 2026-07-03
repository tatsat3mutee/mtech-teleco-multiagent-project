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
CREATE TABLE IF NOT EXISTS provider_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT    NOT NULL,
    provider_group TEXT,
    model         TEXT,
    event         TEXT,
    trace_name    TEXT
);
CREATE INDEX IF NOT EXISTS idx_inferences_ts ON inferences(timestamp);
CREATE INDEX IF NOT EXISTS idx_inferences_type ON inferences(anomaly_type);
CREATE INDEX IF NOT EXISTS idx_provider_events_ts ON provider_events(timestamp);
"""

# Columns added after the original release — applied via guarded ALTER TABLE
# so existing databases upgrade in place.
_MIGRATION_COLUMNS = [
    ("investigator_ms", "REAL"),
    ("reasoner_ms", "REAL"),
    ("critic_ms", "REAL"),
    ("reporter_ms", "REAL"),
    ("prompt_tokens", "INTEGER"),
    ("completion_tokens", "INTEGER"),
    ("review_required", "INTEGER"),
]

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
    for col, ctype in _MIGRATION_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE inferences ADD COLUMN {col} {ctype}")
        except sqlite3.OperationalError:
            pass  # column already exists
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
    stage_timings: Optional[dict] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    review_required: Optional[bool] = None,
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
        st = stage_timings or {}
        with _conn() as c:
            c.execute(
                """INSERT INTO inferences
                   (timestamp, anomaly_id, anomaly_type, severity, root_cause,
                    confidence, latency_ms, provider, model, source,
                    investigator_ms, reasoner_ms, critic_ms, reporter_ms,
                    prompt_tokens, completion_tokens, review_required)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
                    st.get("investigator_ms"),
                    st.get("reasoner_ms"),
                    st.get("critic_ms"),
                    st.get("reporter_ms"),
                    int(prompt_tokens) if prompt_tokens is not None else None,
                    int(completion_tokens) if completion_tokens is not None else None,
                    (1 if review_required else 0) if review_required is not None else None,
                ),
            )
    except Exception as e:
        # Logging must never break inference
        print(f"[inference_log] write failed: {e}")


def log_provider_event(group: str, model: str, event: str, trace_name: str = "") -> None:
    """Record a provider success/rate_limit/timeout/error event. Best-effort."""
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO provider_events (timestamp, provider_group, model, event, trace_name) "
                "VALUES (?,?,?,?,?)",
                (
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    str(group), str(model)[:120], str(event), str(trace_name)[:80],
                ),
            )
    except Exception as e:
        print(f"[inference_log] provider event write failed: {e}")


def provider_stats():
    """Aggregate provider resilience stats for the dashboard."""
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT provider_group, event, COUNT(*) FROM provider_events "
                "GROUP BY provider_group, event"
            ).fetchall()
            out: dict = {}
            for group, event, n in rows:
                out.setdefault(group, {})[event] = n
            return out
    except Exception as e:
        print(f"[inference_log] provider stats failed: {e}")
        return {}


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
