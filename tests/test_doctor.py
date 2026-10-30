"""Unit tests for ghost doctor command."""

from haunted_terminal.config import GhostConfig
from haunted_terminal.doctor import run_doctor


def test_doctor_runs_with_unreachable_host(capsys):
    cfg = GhostConfig(
        ollama_host="http://127.0.0.1:59998",
        model="nonexistent-model",
    )
    passed = run_doctor(cfg)
    # Should report failure for unreachable host
    assert not passed
    captured = capsys.readouterr()
    assert "GHOST DOCTOR DIAGNOSTICS" in captured.out
    assert "UNREACHABLE" in captured.out
    assert "Troubleshooting Steps" in captured.out
