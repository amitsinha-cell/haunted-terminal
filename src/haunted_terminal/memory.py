"""Memory extraction and whisper deduplication using SQLite history."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from haunted_terminal.db import get_db


def _format_relative_time(iso_ts: str) -> str:
    """Format an ISO timestamp into a spooky relative time string."""
    try:
        dt = datetime.fromisoformat(iso_ts)
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        diff = now - dt
        seconds = max(0, int(diff.total_seconds()))

        hour_str = dt.strftime("%I:%M %p").lstrip("0")
        day_str = dt.strftime("%A")

        if seconds < 60:
            return f"moments ago at {hour_str}"
        elif seconds < 3600:
            mins = seconds // 60
            return f"{mins} minute{'s' if mins != 1 else ''} ago at {hour_str}"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago at {hour_str}"
        elif seconds < 86400 * 7:
            days = seconds // 86400
            return f"{days} day{'s' if days != 1 else ''} ago on {day_str} at {hour_str}"
        else:
            return f"long ago on {dt.strftime('%b %d')} at {hour_str}"
    except Exception:
        return "in a past cycle"


def get_relevant_memories(
    command: str,
    cwd: str,
    session_id: str,
    limit: int = 3,
    db_path: Optional[Path] = None,
) -> list[str]:
    """Retrieve up to `limit` relevant memories from past commands.

    Finds:
    1. Past executions of the same command.
    2. Recent failures in the same cwd.
    3. Old visits to this cwd.
    """
    memories: list[str] = []

    try:
        with get_db(db_path) as conn:
            # 1. Check if same command was run previously (excluding the current command in flight)
            cur = conn.execute(
                """
                SELECT command, exit_code, timestamp FROM commands
                WHERE command = ?
                ORDER BY id DESC
                LIMIT 5;
                """,
                (command,),
            )
            rows = cur.fetchall()
            for row in rows:
                if len(memories) >= limit:
                    break
                rel_time = _format_relative_time(row["timestamp"])
                code = row["exit_code"]
                if code == 0:
                    memories.append(f"You ran '{row['command']}' {rel_time} and survived (code 0)")
                else:
                    memories.append(f"You ran '{row['command']}' {rel_time} and it died (exit code {code})")

            # 2. Check for recent failures in this working directory
            if len(memories) < limit:
                cur = conn.execute(
                    """
                    SELECT command, exit_code, timestamp FROM commands
                    WHERE cwd = ? AND exit_code != 0 AND command != ?
                    ORDER BY id DESC
                    LIMIT 3;
                    """,
                    (cwd, command),
                )
                for row in cur.fetchall():
                    if len(memories) >= limit:
                        break
                    rel_time = _format_relative_time(row["timestamp"])
                    memories.append(
                        f"In this directory, '{row['command']}' perished {rel_time} (exit {row['exit_code']})"
                    )

            # 3. Check when this directory was first/last visited if no other memories
            if len(memories) < limit:
                cur = conn.execute(
                    """
                    SELECT timestamp FROM commands
                    WHERE cwd = ?
                    ORDER BY id ASC
                    LIMIT 1;
                    """,
                    (cwd,),
                )
                first_row = cur.fetchone()
                if first_row:
                    rel_time = _format_relative_time(first_row["timestamp"])
                    memories.append(f"You first disturbed this directory {rel_time}")

    except Exception:
        pass

    return memories[:limit]


def is_recent_whisper(
    whisper: str,
    session_id: str,
    db_path: Optional[Path] = None,
) -> bool:
    """Check if the exact whisper has already been spoken in this session."""
    if not whisper or not session_id:
        return False

    cleaned = " ".join(whisper.strip().lower().split())
    try:
        with get_db(db_path) as conn:
            cur = conn.execute(
                """
                SELECT whisper FROM whispers
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT 50;
                """,
                (session_id,),
            )
            for row in cur.fetchall():
                prev = " ".join(row["whisper"].strip().lower().split())
                if cleaned == prev or (len(cleaned) > 10 and cleaned in prev):
                    return True
    except Exception:
        pass
    return False


def get_last_visit_time_for_cwd(
    cwd: str,
    current_command_id: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> Optional[float]:
    """Get the epoch timestamp of the previous visit to this directory."""
    try:
        with get_db(db_path) as conn:
            query = """
                SELECT timestamp FROM commands
                WHERE cwd = ?
            """
            params: list[object] = [cwd]
            if current_command_id is not None:
                query += " AND id < ? ORDER BY id DESC LIMIT 1;"
                params.append(current_command_id)
            else:
                query += " ORDER BY id DESC LIMIT 1 OFFSET 1;"

            cur = conn.execute(query, params)
            row = cur.fetchone()
            if row:
                dt = datetime.fromisoformat(row["timestamp"])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.timestamp()
    except Exception:
        pass
    return None
