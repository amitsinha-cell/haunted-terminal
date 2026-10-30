"""Unit tests for trigger evaluation logic."""

import pytest
from haunted_terminal.triggers import should_trigger


def test_trigger_non_zero_exit():
    triggered, reason = should_trigger(command="ls", exit_code=1)
    assert triggered
    assert "non-zero" in reason


def test_trigger_sudo():
    triggered, reason = should_trigger(command="sudo systemctl restart nginx", exit_code=0)
    assert triggered
    assert "sudo" in reason

    # Pipeline with sudo
    triggered2, reason2 = should_trigger(command="echo foo | sudo tee /etc/bar", exit_code=0)
    assert triggered2
    assert "sudo" in reason2


def test_trigger_rm_destructive():
    for cmd in ["rm -rf /tmp/junk", "rm -fr .git", "rm -r node_modules", "rmdir old"]:
        triggered, reason = should_trigger(command=cmd, exit_code=0)
        assert triggered, f"Failed for {cmd}"
        assert "destructive" in reason


def test_trigger_git_force():
    for cmd in ["git push origin main --force", "git push -f", "git push --force-with-lease"]:
        triggered, reason = should_trigger(command=cmd, exit_code=0)
        assert triggered, f"Failed for {cmd}"
        assert "force" in reason


def test_trigger_git_reset_hard():
    triggered, reason = should_trigger(command="git reset --hard HEAD~1", exit_code=0)
    assert triggered
    assert "git reset hard" in reason


def test_trigger_long_running():
    triggered, reason = should_trigger(command="make build", exit_code=0, duration=31.5)
    assert triggered
    assert "long duration" in reason

    triggered_short, _ = should_trigger(command="make build", exit_code=0, duration=2.5, random_roll=0.99)
    assert not triggered_short


def test_trigger_idle_awakening():
    # 31 minutes idle = 1860 seconds
    triggered, reason = should_trigger(command="ls", exit_code=0, idle_time=1860.0)
    assert triggered
    assert "idle" in reason

    # 10 minutes idle
    triggered_recent, _ = should_trigger(command="ls", exit_code=0, idle_time=600.0, random_roll=0.99)
    assert not triggered_recent


def test_trigger_forgotten_directory():
    triggered, reason = should_trigger(command="cd /archive", exit_code=0, days_since_dir_visit=35.0)
    assert triggered
    assert "forgotten directory" in reason

    triggered_recent_dir, _ = should_trigger(command="cd /recent", exit_code=0, days_since_dir_visit=2.0, random_roll=0.99)
    assert not triggered_recent_dir


def test_probabilistic_scaling_by_level():
    # With roll = 0.08:
    # Level 0 (prob 0.06): 0.08 >= 0.06 -> quiet
    tr_lvl0, _ = should_trigger(command="echo hi", exit_code=0, level=0, random_roll=0.08)
    assert not tr_lvl0

    # Level 1 (prob 0.10): 0.08 < 0.10 -> triggered
    tr_lvl1, _ = should_trigger(command="echo hi", exit_code=0, level=1, random_roll=0.08)
    assert tr_lvl1

    # Level 5 (prob 0.40): roll 0.35 -> triggered
    tr_lvl5, _ = should_trigger(command="echo hi", exit_code=0, level=5, random_roll=0.35)
    assert tr_lvl5

    # Level 2 (prob 0.125): roll 0.15 -> quiet
    tr_lvl2, _ = should_trigger(command="echo hi", exit_code=0, level=2, random_roll=0.15)
    assert not tr_lvl2
