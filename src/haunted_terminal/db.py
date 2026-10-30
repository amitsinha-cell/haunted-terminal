"""SQLite database management for Haunted Terminal history and memory."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

from haunted_terminal.config import get_db_path


def init_db(db_path: Optional[Path] = None) -> Path:
    """Initialize SQLite database with WAL mode and tables."""
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                command TEXT NOT NULL,
                exit_code INTEGER NOT NULL,
                duration REAL NOT NULL,
                cwd TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS whispers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                command_id INTEGER,
                whisper TEXT NOT NULL,
                possession_level INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (command_id) REFERENCES commands (id)
            );
            """
        )

        # Indices for memory queries
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_commands_cwd ON commands(cwd);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_commands_cmd ON commands(command);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_commands_time ON commands(timestamp);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_whispers_session ON whispers(session_id);"
        )
        conn.commit()

    return path


@contextmanager
def get_db(db_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite database connection."""
    path = db_path or get_db_path()
    if not path.exists():
        init_db(path)
    conn = sqlite3.connect(path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def record_command(
    session_id: str,
    command: str,
    exit_code: int,
    duration: float,
    cwd: str,
    timestamp: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Record an executed command in history. Returns new row id."""
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO commands (session_id, command, exit_code, duration, cwd, timestamp)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (session_id, command, exit_code, duration, cwd, ts),
        )
        conn.commit()
        return cursor.lastrowid or 0


def record_whisper(
    session_id: str,
    command_id: Optional[int],
    whisper: str,
    possession_level: int,
    timestamp: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Record a model whisper in history. Returns new row id."""
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO whispers (session_id, command_id, whisper, possession_level, timestamp)
            VALUES (?, ?, ?, ?, ?);
            """,
            (session_id, command_id, whisper, possession_level, ts),
        )
        conn.commit()
        return cursor.lastrowid or 0


def get_history_stats(db_path: Optional[Path] = None) -> dict[str, int]:
    """Retrieve history count and whisper count."""
    try:
        with get_db(db_path) as conn:
            cmd_count = conn.execute("SELECT COUNT(*) FROM commands;").fetchone()[0]
            whisper_count = conn.execute("SELECT COUNT(*) FROM whispers;").fetchone()[0]
            return {"commands": cmd_count, "whispers": whisper_count}
    except Exception:
        return {"commands": 0, "whispers": 0}
