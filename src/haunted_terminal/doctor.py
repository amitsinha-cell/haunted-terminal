"""Diagnostic and doctor checks for Haunted Terminal."""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

import httpx

from haunted_terminal.config import (
    GhostConfig,
    auto_detect_model,
    get_config_file,
    get_data_dir,
    get_db_path,
    load_config,
    load_state,
)
from haunted_terminal.db import get_history_stats, init_db
from haunted_terminal.ollama import check_ollama_status


def run_doctor(config: Optional[GhostConfig] = None) -> bool:
    """Run full diagnostic suite and print actionable guidance.

    Returns:
        True if all critical checks pass, False otherwise.
    """
    cfg = config or load_config()
    state = load_state()

    print("\033[1;35m======================================================\033[0m")
    print("\033[1;35m             👻 GHOST DOCTOR DIAGNOSTICS             \033[0m")
    print("\033[1;35m======================================================\033[0m\n")

    all_passed = True

    # 1. State check
    if state.enabled:
        print("  \033[32m[✓]\033[0m Ghost Status: \033[1mENABLED\033[0m (The veil is thin)")
    else:
        print("  \033[33m[!]\033[0m Ghost Status: \033[1mDISABLED\033[0m (Run 'ghost on' to awake)")

    if state.pinned_level is not None:
        print(f"      Possession Level: Pinned at {state.pinned_level}")
    else:
        print("      Possession Level: Dynamic (auto-adapting)")

    # 2. Database check
    db_path = get_db_path()
    try:
        init_db(db_path)
        stats = get_history_stats(db_path)
        print(f"  \033[32m[✓]\033[0m Memory Database: {db_path}")
        print(f"      Recorded commands: {stats['commands']} | Whispers: {stats['whispers']}")
    except Exception as e:
        all_passed = False
        print(f"  \033[31m[✗]\033[0m Memory Database: Failed ({e})")
        print("      \033[33mFix: Ensure write permissions to ~/.local/share/ghost\033[0m")

    # 3. Ollama Connectivity Check
    host = cfg.ollama_host
    connected, conn_err, available_models = check_ollama_status(host, timeout=2.0)

    if connected:
        print(f"  \033[32m[✓]\033[0m Ollama Connection: Reachable at {host}")
    else:
        all_passed = False
        print(f"  \033[31m[✗]\033[0m Ollama Connection: UNREACHABLE at {host}")
        print(f"      Details: {conn_err}")
        print("      \033[33mTroubleshooting Steps:\033[0m")
        print("      1. Start Ollama locally: run 'ollama serve' or start Ollama app")
        print("      2. If running inside WSL2, export your Windows host IP:")
        print("         export OLLAMA_HOST=http://$(ip route | awk '/default/ {print $3}'):11434")
        print(f"      3. Check configured URL in ~/.config/ghost/config.json or $OLLAMA_HOST")
        print()

    # 4. Model Availability Check
    target_model = cfg.model
    if not target_model:
        target_model = auto_detect_model(host)
        cfg.model = target_model

    if connected:
        model_found = any(m.lower() == target_model.lower() for m in available_models)
        if model_found:
            print(f"  \033[32m[✓]\033[0m Configured Model: '{target_model}' is available")
        else:
            all_passed = False
            print(f"  \033[31m[✗]\033[0m Configured Model: '{target_model}' NOT FOUND in Ollama")
            print(f"      Available models: {', '.join(available_models) if available_models else 'None'}")
            print("      \033[33mFix: Pull the model or change your configuration:\033[0m")
            print(f"      Run: ollama pull {target_model}")
            if available_models:
                print(f"      Or use an available model: export GHOST_MODEL={available_models[0]}")
            print()

        # 5. Model Latency & Inference Test
        if model_found:
            print(f"  \033[34m[~]\033[0m Testing whisper latency for '{target_model}'...")
            t0 = time.time()
            try:
                payload = {
                    "model": target_model,
                    "messages": [
                        {"role": "system", "content": "You are a ghost. Whisper one single spooky word."},
                        {"role": "user", "content": "ping"},
                    ],
                    "stream": False,
                    "options": {"num_predict": 10, "temperature": 0.7},
                    "keep_alive": cfg.keep_alive,
                }
                with httpx.Client(timeout=4.0) as client:
                    resp = client.post(f"{host.rstrip('/')}/api/chat", json=payload)
                    latency = (time.time() - t0) * 1000.0

                    if resp.status_code == 200:
                        data = resp.json()
                        content = data.get("message", {}).get("content", "").strip()
                        if not content and "thinking" in data.get("message", {}):
                            content = "awake"
                        if latency <= 1500:
                            print(f"  \033[32m[✓]\033[0m Model Latency: {latency:.1f}ms (under 1.5s timeout budget)")
                        else:
                            print(f"  \033[33m[!]\033[0m Model Latency: {latency:.1f}ms (slow start; subsequent warm calls will be faster)")
                        print(f"      Sample whisper: \"\033[2;3m{content}\033[0m\"")
                    else:
                        all_passed = False
                        print(f"  \033[31m[✗]\033[0m Model Test: Ollama returned HTTP {resp.status_code}")
            except httpx.TimeoutException:
                all_passed = False
                print(f"  \033[31m[✗]\033[0m Model Test: Timed out after 4.0s (model loading or overloaded)")
                print("      \033[33mFix: Run 'ollama run " + target_model + "' once to warm into VRAM\033[0m")
            except Exception as e:
                all_passed = False
                print(f"  \033[31m[✗]\033[0m Model Test: {e}")

    # 6. Shell Hook Installation Check
    home = Path.home()
    rc_files = [home / ".bashrc", home / ".zshrc"]
    found_hook = False
    for rc in rc_files:
        if rc.exists():
            try:
                content = rc.read_text(encoding="utf-8", errors="ignore")
                if "ghost init" in content:
                    found_hook = True
                    print(f"  \033[32m[✓]\033[0m Shell Hook: Found in {rc}")
            except Exception:
                pass

    if not found_hook:
        print("  \033[33m[!]\033[0m Shell Hook: Not detected in ~/.bashrc or ~/.zshrc")
        print("      To activate Ghost in your shell, run:")
        print("      ghost install bash   # or: ghost install zsh")
        print("      or add this to your rc file:")
        print("      eval \"$(ghost init bash)\"")

    print("\n\033[1;35m======================================================\033[0m")
    if all_passed:
        print("  \033[1;32mAll systems functional. The terminal is haunted.\033[0m")
    else:
        print("  \033[1;33mSome checks need attention. See guidance above.\033[0m")
    print("\033[1;35m======================================================\033[0m\n")

    return all_passed
