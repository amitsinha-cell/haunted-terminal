"""Unit tests for ghost CLI commands."""

import argparse
from pathlib import Path
import pytest

from haunted_terminal.cli import (
    cmd_init,
    cmd_level,
    cmd_off,
    cmd_on,
    cmd_pending,
    cmd_status,
    cmd_whisper,
    cmd_install,
    cmd_exorcise,
    main,
)
from haunted_terminal.config import (
    get_pending_whisper_path,
    load_state,
    save_state,
)


def test_cli_on_and_off(capsys):
    rc = main(["off"])
    assert rc == 0
    state = load_state()
    assert not state.enabled

    rc = main(["on"])
    assert rc == 0
    state = load_state()
    assert state.enabled


def test_cli_level(capsys):
    rc = main(["level", "4"])
    assert rc == 0
    state = load_state()
    assert state.pinned_level == 4

    rc = main(["level", "auto"])
    assert rc == 0
    state = load_state()
    assert state.pinned_level is None

    # Invalid level
    rc = main(["level", "99"])
    assert rc == 1


def test_cli_status(capsys):
    rc = main(["status"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "HAUNTED TERMINAL STATUS" in captured.out
    assert "Ollama Host" in captured.out


def test_cli_init(capsys):
    rc = main(["init", "bash"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "PROMPT_COMMAND" in captured.out


def test_cli_pending(capsys):
    pending_path = get_pending_whisper_path()
    pending_path.write_text("A ghostly echo lingers.", encoding="utf-8")

    rc = main(["pending"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "A ghostly echo lingers." in captured.out
    # File should be cleared after reading
    assert not pending_path.exists()


def test_cli_whisper_silent_when_off(capsys):
    main(["off"])
    capsys.readouterr()  # Flush output from 'ghost off'
    rc = main([
        "whisper",
        "--cmd", "ls -la",
        "--exit-code", "0",
        "--duration", "0.01",
        "--cwd", "/tmp",
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    # Re-enable
    main(["on"])


def test_cli_install_and_exorcise(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bashrc = tmp_path / ".bashrc"
    bashrc.write_text("# existing bashrc content\n", encoding="utf-8")

    # Install
    args = argparse.Namespace(shell="bash", cmd_name="ghost")
    rc = cmd_install(args)
    assert rc == 0
    content = bashrc.read_text(encoding="utf-8")
    assert 'eval "$(ghost init bash)"' in content

    # Backup should exist
    assert (tmp_path / ".bashrc.bak").exists()

    # Idempotent install
    rc2 = cmd_install(args)
    assert rc2 == 0

    # Exorcise
    args_exo = argparse.Namespace(delete_data=False)
    rc_exo = cmd_exorcise(args_exo)
    assert rc_exo == 0
    content_after = bashrc.read_text(encoding="utf-8")
    assert 'ghost init' not in content_after
