"""Unit tests for SQLite database and memory retrieval."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from haunted_terminal.db import init_db, record_command, record_whisper, get_history_stats
from haunted_terminal.memory import (
    get_relevant_memories,
    is_recent_whisper,
    get_last_visit_time_for_cwd,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    db_file = tmp_path / "test_history.db"
    init_db(db_file)
    return db_file


def test_record_command_and_stats(temp_db: Path):
    cmd_id = record_command(
        session_id="sess_1",
        command="git status",
        exit_code=0,
        duration=0.04,
        cwd="/home/user/project",
        db_path=temp_db,
    )
    assert cmd_id > 0

    stats = get_history_stats(temp_db)
    assert stats["commands"] == 1
    assert stats["whispers"] == 0

    whisper_id = record_whisper(
        session_id="sess_1",
        command_id=cmd_id,
        whisper="The branches whisper your name.",
        possession_level=2,
        db_path=temp_db,
    )
    assert whisper_id > 0

    stats = get_history_stats(temp_db)
    assert stats["commands"] == 1
    assert stats["whispers"] == 1


def test_relevant_memories(temp_db: Path):
    now = datetime.now(timezone.utc)
    ts_yesterday = (now - timedelta(days=1)).isoformat()

    record_command(
        session_id="sess_old",
        command="npm test",
        exit_code=1,
        duration=1.2,
        cwd="/home/user/app",
        timestamp=ts_yesterday,
        db_path=temp_db,
    )

    memories = get_relevant_memories(
        command="npm test",
        cwd="/home/user/app",
        session_id="sess_new",
        limit=3,
        db_path=temp_db,
    )
    assert len(memories) >= 1
    assert "npm test" in memories[0]
    assert "died" in memories[0] or "perished" in memories[0]


def test_whisper_deduplication(temp_db: Path):
    whisper_text = "The veil thins as the darkness grows."
    record_whisper(
        session_id="sess_dup",
        command_id=1,
        whisper=whisper_text,
        possession_level=3,
        db_path=temp_db,
    )

    assert is_recent_whisper(whisper_text, session_id="sess_dup", db_path=temp_db)
    assert is_recent_whisper(whisper_text.upper(), session_id="sess_dup", db_path=temp_db)
    # Different session should not trigger deduplication
    assert not is_recent_whisper(whisper_text, session_id="sess_other", db_path=temp_db)


def test_get_last_visit_time_for_cwd(temp_db: Path):
    t1 = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    t2 = datetime.now(timezone.utc).isoformat()

    record_command("sess_1", "ls", 0, 0.01, "/old/dir", timestamp=t1, db_path=temp_db)
    id2 = record_command("sess_1", "ls", 0, 0.01, "/old/dir", timestamp=t2, db_path=temp_db)

    last_visit = get_last_visit_time_for_cwd("/old/dir", current_command_id=id2, db_path=temp_db)
    assert last_visit is not None
    # Check that it's around 40 days ago
    assert (datetime.now(timezone.utc).timestamp() - last_visit) > 35 * 86400
