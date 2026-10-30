"""Unit tests for possession levels and prompts."""

from datetime import datetime, timezone
import pytest

from haunted_terminal.levels import (
    calculate_possession_level,
    get_system_prompt,
    analyze_command_hint,
    build_user_prompt,
)


def test_level_pinned_override():
    # Pinned level should override any dynamic inputs
    lvl = calculate_possession_level(
        session_start_time=0.0,
        failure_streak=10,
        pinned_level=2,
    )
    assert lvl == 2

    # Clamp bounds
    assert calculate_possession_level(0.0, 0, pinned_level=99) == 5
    assert calculate_possession_level(0.0, 0, pinned_level=-5) == 0


def test_level_late_night_boost():
    # 3 AM (witching hour)
    t_3am = datetime(2026, 10, 31, 3, 0, tzinfo=timezone.utc)
    t_midday = datetime(2026, 10, 31, 14, 0, tzinfo=timezone.utc)

    lvl_night = calculate_possession_level(
        session_start_time=t_3am.timestamp(),
        failure_streak=0,
        current_time=t_3am,
    )
    lvl_day = calculate_possession_level(
        session_start_time=t_midday.timestamp(),
        failure_streak=0,
        current_time=t_midday,
    )

    assert lvl_night > lvl_day


def test_level_failure_streak():
    t_midday = datetime(2026, 10, 31, 14, 0, tzinfo=timezone.utc)
    lvl_fail = calculate_possession_level(
        session_start_time=t_midday.timestamp(),
        failure_streak=4,
        current_time=t_midday,
    )
    lvl_success = calculate_possession_level(
        session_start_time=t_midday.timestamp(),
        failure_streak=0,
        current_time=t_midday,
    )
    assert lvl_fail > lvl_success


def test_system_prompt_retrieval():
    for lvl in range(6):
        prompt = get_system_prompt(lvl)
        assert f"Level {lvl}" in prompt or "Haunted Terminal" in prompt
        assert "ONE single line" in prompt


def test_analyze_command_hint_typo():
    hint = analyze_command_hint("sl -la", exit_code=127)
    assert hint is not None
    assert "ls" in hint


def test_analyze_command_hint_missing_file():
    hint = analyze_command_hint("cat non_existent_file.txt", exit_code=1)
    assert hint is not None
    assert "non_existent_file.txt" in hint


def test_analyze_command_hint_git():
    hint = analyze_command_hint("git push origin main", exit_code=1)
    assert hint is not None
    assert "git" in hint.lower()


def test_build_user_prompt():
    prompt = build_user_prompt(
        command="rm -rf /tmp/test",
        exit_code=0,
        duration=0.12,
        cwd="/home/user",
        memories=["You ran this yesterday"],
        hint=None,
    )
    assert "Command: rm -rf /tmp/test" in prompt
    assert "Exit code: 0" in prompt
    assert "Past history:" in prompt
    assert "You ran this yesterday" in prompt
