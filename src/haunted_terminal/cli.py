"""CLI commands and entry point for Haunted Terminal (ghost)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from haunted_terminal.config import (
    GhostConfig,
    GhostState,
    auto_detect_model,
    get_config_file,
    get_data_dir,
    get_db_path,
    get_pending_whisper_path,
    get_state_file,
    load_config,
    load_state,
    save_config,
    save_state,
)
from haunted_terminal.db import get_history_stats, init_db, record_command, record_whisper
from haunted_terminal.doctor import run_doctor
from haunted_terminal.hooks import get_hook_script
from haunted_terminal.levels import (
    analyze_command_hint,
    build_user_prompt,
    calculate_possession_level,
    get_system_prompt,
)
from haunted_terminal.memory import (
    get_last_visit_time_for_cwd,
    get_relevant_memories,
    is_recent_whisper,
)
from haunted_terminal.ollama import call_whisper_model, format_whisper
from haunted_terminal.redact import redact_secrets, sanitize_model_output


def cmd_init(args: argparse.Namespace) -> int:
    """Print shell integration hook code."""
    shell = args.shell or os.environ.get("SHELL", "bash").split("/")[-1]
    try:
        script = get_hook_script(shell)
        print(script)
        return 0
    except ValueError as e:
        print(f"\033[31mError: {e}\033[0m", file=sys.stderr)
        return 1


def cmd_on(args: argparse.Namespace) -> int:
    """Enable haunted terminal."""
    state = load_state()
    state.enabled = True
    save_state(state)
    print("\033[2;3;90m👻 The veil thins. The ghost is listening...\033[0m")
    return 0


def cmd_off(args: argparse.Namespace) -> int:
    """Disable haunted terminal commentary."""
    state = load_state()
    state.enabled = False
    save_state(state)
    print("\033[2;3;90m👻 The ghost retreats into the cold shadows.\033[0m")
    return 0


def cmd_level(args: argparse.Namespace) -> int:
    """Get or set possession level (0-5, or auto/reset)."""
    state = load_state()

    if args.level is None:
        # Display current level
        current_lvl = calculate_possession_level(
            session_start_time=0.0,
            failure_streak=state.failure_streak,
            pinned_level=state.pinned_level,
        )
        if state.pinned_level is not None:
            print(f"👻 Possession level: \033[1m{state.pinned_level}\033[0m (pinned)")
        else:
            print(f"👻 Possession level: \033[1m{current_lvl}\033[0m (dynamic, auto-adapting)")
        return 0

    val = args.level.strip().lower()
    if val in ("auto", "reset", "clear"):
        state.pinned_level = None
        save_state(state)
        print("👻 Possession level unpinned. Ghost will adapt dynamically.")
        return 0

    try:
        lvl = int(val)
        if not (0 <= lvl <= 5):
            print("Error: Level must be between 0 and 5, or 'auto'.", file=sys.stderr)
            return 1
        state.pinned_level = lvl
        save_state(state)
        print(f"👻 Possession level pinned at \033[1m{lvl}\033[0m.")
        return 0
    except ValueError:
        print(f"Error: Invalid level '{args.level}'. Must be 0-5 or 'auto'.", file=sys.stderr)
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Display ghost status and session stats."""
    cfg = load_config()
    state = load_state()
    db_path = get_db_path()
    stats = get_history_stats(db_path)

    active_model = cfg.model or auto_detect_model(cfg.ollama_host)
    current_lvl = calculate_possession_level(
        session_start_time=0.0,
        failure_streak=state.failure_streak,
        pinned_level=state.pinned_level,
    )

    print("\033[1;35m======================================================\033[0m")
    print("\033[1;35m               👻 HAUNTED TERMINAL STATUS             \033[0m")
    print("\033[1;35m======================================================\033[0m")
    status_str = "\033[32mENABLED\033[0m" if state.enabled else "\033[31mDISABLED\033[0m"
    print(f"  State:            {status_str}")
    lvl_str = f"{current_lvl} (pinned)" if state.pinned_level is not None else f"{current_lvl} (dynamic)"
    print(f"  Possession Level: {lvl_str}")
    print(f"  Failure Streak:   {state.failure_streak}")
    print(f"  Ollama Host:      {cfg.ollama_host}")
    print(f"  Active Model:     {active_model}")
    print(f"  History Database: {db_path}")
    print(f"  Total Commands:   {stats['commands']}")
    print(f"  Total Whispers:   {stats['whispers']}")
    print("\033[1;35m======================================================\033[0m")
    return 0


def cmd_pending(args: argparse.Namespace) -> int:
    """Check for and display any saved late whisper, then clear it."""
    pending_file = get_pending_whisper_path()
    if pending_file.exists():
        try:
            whisper = pending_file.read_text(encoding="utf-8").strip()
            pending_file.unlink(missing_ok=True)
            if whisper:
                print(format_whisper(whisper))
                sys.stdout.flush()
        except Exception:
            pass
    return 0


def cmd_whisper(args: argparse.Namespace) -> int:
    """Internal handler invoked by shell hooks after each command."""
    # 1. Quick enabled check (< 2ms)
    state = load_state()
    if not state.enabled or os.environ.get("GHOST_DISABLED") == "1":
        return 0

    cmd_raw = args.cmd or ""
    exit_code = int(args.exit_code or 0)
    duration = float(args.duration or 0.0)
    cwd = args.cwd or os.getcwd()
    session_id = args.session or state.session_id or "default"

    # 2. Redact secrets before anything touches DB or model (< 2ms)
    redacted_cmd = redact_secrets(cmd_raw)
    now_ts = time.time()
    iso_ts = datetime.now(timezone.utc).isoformat()

    # 3. Record in SQLite history (< 3ms)
    db_path = get_db_path()
    try:
        cmd_id = record_command(
            session_id=session_id,
            command=redacted_cmd,
            exit_code=exit_code,
            duration=duration,
            cwd=cwd,
            timestamp=iso_ts,
            db_path=db_path,
        )
    except Exception:
        cmd_id = 0

    # 4. Calculate idle time and forgotten directory check
    idle_time = (now_ts - state.last_command_time) if state.last_command_time > 0 else 0.0
    state.last_command_time = now_ts

    days_since_dir: Optional[float] = None
    if cwd:
        last_visit = get_last_visit_time_for_cwd(cwd, current_command_id=cmd_id, db_path=db_path)
        if last_visit:
            days_since_dir = max(0.0, (now_ts - last_visit) / 86400.0)

    # 5. Evaluate possession level
    lvl = calculate_possession_level(
        session_start_time=now_ts - (state.failure_streak * 60),
        failure_streak=state.failure_streak,
        pinned_level=state.pinned_level,
    )

    # 6. Check triggers (< 2ms)
    from haunted_terminal.triggers import should_trigger

    should_speak, reason = should_trigger(
        command=redacted_cmd,
        exit_code=exit_code,
        duration=duration,
        idle_time=idle_time,
        days_since_dir_visit=days_since_dir,
        level=lvl,
    )

    # Update failure streak
    if exit_code != 0:
        state.failure_streak += 1
    else:
        state.failure_streak = max(0, state.failure_streak - 1)
    save_state(state)

    if not should_speak:
        # Total time when quiet: < 15ms
        return 0

    # 7. Ghost decided to speak!
    cfg = load_config()
    if not cfg.model:
        cfg.model = auto_detect_model(cfg.ollama_host)

    memories = get_relevant_memories(redacted_cmd, cwd, session_id, limit=3, db_path=db_path)
    hint = analyze_command_hint(redacted_cmd, exit_code)
    sys_prompt = get_system_prompt(lvl)
    user_prompt = build_user_prompt(redacted_cmd, exit_code, duration, cwd, memories, hint)

    # Call Ollama: we use sync_timeout budget so user's prompt is never blocked
    import concurrent.futures

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        call_whisper_model,
        sys_prompt,
        user_prompt,
        cfg,
        cfg.timeout,
    )

    try:
        # Wait up to sync_timeout (e.g. 0.8s)
        whisper = future.result(timeout=cfg.sync_timeout)
        if whisper and not is_recent_whisper(whisper, session_id, db_path=db_path):
            record_whisper(session_id, cmd_id, whisper, lvl, db_path=db_path)
            print(format_whisper(whisper))
            sys.stdout.flush()
    except concurrent.futures.TimeoutError:
        # Sync budget exceeded! Don't block the user's prompt.
        # Detach background worker to save late whisper for next prompt
        _spawn_late_worker(sys_prompt, user_prompt, cfg, session_id, cmd_id, lvl)
    except Exception:
        pass
    finally:
        executor.shutdown(wait=False)

    return 0


def _spawn_late_worker(
    sys_prompt: str,
    user_prompt: str,
    config: GhostConfig,
    session_id: str,
    cmd_id: int,
    lvl: int,
) -> None:
    """Spawn a detached background process to finish late whisper and save it."""
    import tempfile

    worker_script = f"""
import sys
from haunted_terminal.config import GhostConfig, get_pending_whisper_path, get_db_path
from haunted_terminal.ollama import call_whisper_model
from haunted_terminal.memory import is_recent_whisper
from haunted_terminal.db import record_whisper

cfg = GhostConfig(
    ollama_host={repr(config.ollama_host)},
    model={repr(config.model)},
    timeout={config.timeout},
    keep_alive={repr(config.keep_alive)},
    num_predict={config.num_predict},
    num_ctx={config.num_ctx},
    temperature={config.temperature},
)
whisper = call_whisper_model({repr(sys_prompt)}, {repr(user_prompt)}, cfg, timeout=cfg.timeout)
if whisper:
    db_path = get_db_path()
    if not is_recent_whisper(whisper, {repr(session_id)}, db_path=db_path):
        record_whisper({repr(session_id)}, {cmd_id}, whisper, {lvl}, db_path=db_path)
        p = get_pending_whisper_path()
        try:
            p.write_text(whisper, encoding='utf-8')
        except Exception:
            pass
"""
    try:
        subprocess.Popen(
            [sys.executable, "-c", worker_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def cmd_install(args: argparse.Namespace) -> int:
    """Install ghost hook into user's shell rc file."""
    shell = args.shell or os.environ.get("SHELL", "bash").split("/")[-1]
    home = Path.home()

    rc_file: Optional[Path] = None
    if "zsh" in shell:
        rc_file = home / ".zshrc"
    elif "bash" in shell:
        rc_file = home / ".bashrc"
    elif "powershell" in shell or "pwsh" in shell:
        # PowerShell profile path
        if os.name == "nt":
            rc_file = home / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1"
        else:
            rc_file = home / ".config" / "powershell" / "Microsoft.PowerShell_profile.ps1"

    if not rc_file:
        print(f"Error: Unknown shell '{shell}'. Supported: bash, zsh, powershell", file=sys.stderr)
        return 1

    rc_file.parent.mkdir(parents=True, exist_ok=True)
    if not rc_file.exists():
        rc_file.touch()

    content = rc_file.read_text(encoding="utf-8", errors="ignore")
    hook_line = f'eval "$({args.cmd_name or "ghost"} init {shell})"'
    if "powershell" in shell or "pwsh" in shell:
        hook_line = f'Invoke-Expression (& {args.cmd_name or "ghost"} init powershell | Out-String)'

    if hook_line in content or "ghost init" in content:
        print(f"Ghost hook is already installed in {rc_file}.")
        return 0

    # Create backup with .bak extension
    backup_file = rc_file.with_suffix(rc_file.suffix + ".bak")
    shutil.copyfile(rc_file, backup_file)
    print(f"Created backup at {backup_file}")

    # Append hook line
    with open(rc_file, "a", encoding="utf-8") as f:
        f.write(f"\n# Haunted Terminal hook\n{hook_line}\n")

    print(f"\033[32mSuccessfully installed Ghost hook in {rc_file}!\033[0m")
    print("Reload your shell or run:")
    print(f"  source {rc_file}")
    return 0


def cmd_exorcise(args: argparse.Namespace) -> int:
    """Remove ghost hooks from rc files and optionally purge data."""
    home = Path.home()
    rc_files = [home / ".bashrc", home / ".zshrc"]
    if os.name == "nt":
        rc_files.append(home / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1")
    else:
        rc_files.append(home / ".config" / "powershell" / "Microsoft.PowerShell_profile.ps1")

    cleaned_any = False
    for rc in rc_files:
        if rc.exists():
            content = rc.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines(keepends=True)
            new_lines = [line for line in lines if "ghost init" not in line and "Haunted Terminal hook" not in line]
            if len(lines) != len(new_lines):
                backup_file = rc.with_suffix(rc.suffix + ".exorcise.bak")
                shutil.copyfile(rc, backup_file)
                rc.write_text("".join(new_lines), encoding="utf-8")
                print(f"Removed ghost hooks from {rc} (backup saved as {backup_file.name})")
                cleaned_any = True

    if not cleaned_any:
        print("No ghost hooks found in common rc files.")

    if args.delete_data:
        data_dir = get_data_dir()
        config_dir = get_config_file().parent
        if data_dir.exists():
            shutil.rmtree(data_dir, ignore_errors=True)
            print(f"Purged database and state at {data_dir}")
        if config_dir.exists():
            shutil.rmtree(config_dir, ignore_errors=True)
            print(f"Purged configuration at {config_dir}")
        print("\033[1;32mExorcism complete. The spirit has vanished entirely.\033[0m")
    else:
        print("\033[32mHooks removed. To delete history database as well, run:\033[0m")
        print("  ghost exorcise --delete-data")

    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Main CLI entry point."""
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        prog="ghost",
        description="Haunted Terminal - Local LLM whispers short commentary after terminal commands.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # init
    p_init = subparsers.add_parser("init", help="Print shell integration hook script")
    p_init.add_argument("shell", nargs="?", default=None, help="Shell type (zsh, bash, powershell)")

    # on
    subparsers.add_parser("on", help="Enable ghost commentary")

    # off
    subparsers.add_parser("off", help="Disable ghost commentary")

    # level
    p_lvl = subparsers.add_parser("level", help="Get or set possession level (0-5, or auto/reset)")
    p_lvl.add_argument("level", nargs="?", default=None, help="Level (0-5) or 'auto'")

    # status
    subparsers.add_parser("status", help="Show ghost status and history statistics")

    # doctor
    subparsers.add_parser("doctor", help="Check Ollama connectivity, model, and shell health")

    # pending
    subparsers.add_parser("pending", help="Print and clear any pending late whispers")

    # whisper (internal hook invocation)
    p_w = subparsers.add_parser("whisper", help="Internal hook for evaluating commands")
    p_w.add_argument("--cmd", default="", help="Command executed")
    p_w.add_argument("--exit-code", default="0", help="Command exit code")
    p_w.add_argument("--duration", default="0", help="Command duration in seconds")
    p_w.add_argument("--cwd", default="", help="Current working directory")
    p_w.add_argument("--session", default="", help="Session ID")

    # install
    p_inst = subparsers.add_parser("install", help="Append hook code to your shell rc file")
    p_inst.add_argument("shell", nargs="?", default=None, help="Shell type (bash, zsh, powershell)")
    p_inst.add_argument("--cmd-name", default="ghost", help="Command binary name")

    # exorcise
    p_exo = subparsers.add_parser("exorcise", help="Remove hooks and purge ghost data")
    p_exo.add_argument("--delete-data", "--all", action="store_true", help="Delete SQLite history and configuration")

    parsed_args = parser.parse_args(argv)

    if parsed_args.command == "init":
        return cmd_init(parsed_args)
    elif parsed_args.command == "on":
        return cmd_on(parsed_args)
    elif parsed_args.command == "off":
        return cmd_off(parsed_args)
    elif parsed_args.command == "level":
        return cmd_level(parsed_args)
    elif parsed_args.command == "status":
        return cmd_status(parsed_args)
    elif parsed_args.command == "doctor":
        return 0 if run_doctor() else 1
    elif parsed_args.command == "pending":
        return cmd_pending(parsed_args)
    elif parsed_args.command == "whisper":
        return cmd_whisper(parsed_args)
    elif parsed_args.command == "install":
        return cmd_install(parsed_args)
    elif parsed_args.command == "exorcise":
        return cmd_exorcise(parsed_args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
