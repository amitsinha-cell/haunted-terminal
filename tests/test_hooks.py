"""Unit tests for shell hook scripts."""

import pytest
from haunted_terminal.hooks import get_hook_script, get_zsh_hook, get_bash_hook, get_powershell_hook


def test_zsh_hook_content():
    hook = get_zsh_hook()
    assert "add-zsh-hook" in hook
    assert "_ghost_preexec" in hook
    assert "_ghost_precmd" in hook
    assert "ghost pending" in hook
    assert "ghost whisper" in hook
    assert "--cmd" in hook
    assert "--exit-code" in hook
    assert "--duration" in hook


def test_bash_hook_content():
    hook = get_bash_hook()
    assert "trap '_ghost_preexec' DEBUG" in hook
    assert "PROMPT_COMMAND" in hook
    assert "_ghost_precmd" in hook
    assert "ghost pending" in hook
    assert "ghost whisper" in hook


def test_powershell_hook_content():
    hook = get_powershell_hook()
    assert "function global:prompt" in hook
    assert "ghost pending" in hook
    assert "ghost whisper" in hook


def test_get_hook_script_dispatch():
    assert get_hook_script("zsh") == get_zsh_hook()
    assert get_hook_script("bash") == get_bash_hook()
    assert get_hook_script("powershell") == get_powershell_hook()
    assert get_hook_script("pwsh") == get_powershell_hook()

    with pytest.raises(ValueError, match="Unsupported shell"):
        get_hook_script("tcsh")
