"""Configuration and state management for Haunted Terminal."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class GhostConfig:
    """Configuration options for Ghost."""

    ollama_host: str = "http://localhost:11434"
    model: str = ""
    timeout: float = 1.5  # Hard timeout in seconds
    sync_timeout: float = 0.8  # Max wait time before detaching to background
    keep_alive: str = "30m"
    num_predict: int = 40
    num_ctx: int = 1024
    temperature: float = 0.7


@dataclass
class GhostState:
    """Persistent runtime state for Ghost (on/off, pinned level, session)."""

    enabled: bool = True
    pinned_level: Optional[int] = None
    session_id: str = ""
    last_command_time: float = 0.0
    failure_streak: int = 0


def get_config_dir() -> Path:
    """Return path to ghost config directory (~/.config/ghost)."""
    custom = os.environ.get("XDG_CONFIG_HOME")
    if custom:
        base = Path(custom)
    else:
        base = Path.home() / ".config"
    path = base / "ghost"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_dir() -> Path:
    """Return path to ghost data directory (~/.local/share/ghost)."""
    custom = os.environ.get("XDG_DATA_HOME")
    if custom:
        base = Path(custom)
    else:
        base = Path.home() / ".local" / "share"
    path = base / "ghost"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_file() -> Path:
    return get_config_dir() / "config.json"


def get_state_file() -> Path:
    return get_data_dir() / "state.json"


def get_db_path() -> Path:
    return get_data_dir() / "history.db"


def get_pending_whisper_path() -> Path:
    return get_data_dir() / "pending_whisper"


def load_config() -> GhostConfig:
    """Load configuration from config.json, environment variables, and defaults."""
    cfg = GhostConfig()
    cfg_file = get_config_file()

    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if "ollama_host" in data:
                        cfg.ollama_host = str(data["ollama_host"])
                    if "model" in data:
                        cfg.model = str(data["model"])
                    if "timeout" in data:
                        cfg.timeout = float(data["timeout"])
                    if "sync_timeout" in data:
                        cfg.sync_timeout = float(data["sync_timeout"])
                    if "keep_alive" in data:
                        cfg.keep_alive = str(data["keep_alive"])
                    if "num_predict" in data:
                        cfg.num_predict = int(data["num_predict"])
                    if "num_ctx" in data:
                        cfg.num_ctx = int(data["num_ctx"])
                    if "temperature" in data:
                        cfg.temperature = float(data["temperature"])
        except Exception:
            pass

    # Environment variables override config file
    env_host = os.environ.get("OLLAMA_HOST")
    if env_host:
        # Normalize host URL (if only port or host:port, ensure scheme)
        if not env_host.startswith("http://") and not env_host.startswith("https://"):
            env_host = f"http://{env_host}"
        cfg.ollama_host = env_host

    env_model = os.environ.get("GHOST_MODEL")
    if env_model:
        cfg.model = env_model

    return cfg


def save_config(cfg: GhostConfig) -> None:
    """Save configuration to config.json."""
    cfg_file = get_config_file()
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, indent=2)


def load_state() -> GhostState:
    """Load persistent state (enabled, pinned level, streak)."""
    state = GhostState()
    state_file = get_state_file()

    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    state.enabled = bool(data.get("enabled", True))
                    pinned = data.get("pinned_level")
                    state.pinned_level = int(pinned) if pinned is not None else None
                    state.session_id = str(data.get("session_id", ""))
                    state.last_command_time = float(data.get("last_command_time", 0.0))
                    state.failure_streak = int(data.get("failure_streak", 0))
        except Exception:
            pass

    return state


def save_state(state: GhostState) -> None:
    """Save persistent state to state.json."""
    state_file = get_state_file()
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(asdict(state), f, indent=2)
    except Exception:
        pass


def auto_detect_model(ollama_host: str = "http://localhost:11434") -> str:
    """Auto-detect suitable model tag from Ollama list or API.

    Detects Gemma 4 E4B (gemma4:e4b), any gemma variant, or falls back to
    any available model.
    """
    # 1. Try querying /api/tags via httpx or urllib
    available_tags: list[str] = []
    try:
        import httpx

        with httpx.Client(timeout=1.0) as client:
            resp = client.get(f"{ollama_host.rstrip('/')}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("models", []):
                    name = m.get("name") or m.get("model")
                    if name:
                        available_tags.append(name)
    except Exception:
        # Fallback to calling `ollama list` CLI if available
        ollama_bin = shutil.which("ollama")
        if ollama_bin:
            try:
                res = subprocess.run(
                    [ollama_bin, "list"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if res.returncode == 0:
                    lines = res.stdout.strip().splitlines()
                    for line in lines[1:]:
                        parts = line.split()
                        if parts:
                            available_tags.append(parts[0])
            except Exception:
                pass

    if not available_tags:
        return "gemma4:e4b"

    # Priority matching:
    # 1. Exact match for gemma4:e4b
    for tag in available_tags:
        if tag.lower() == "gemma4:e4b":
            return tag

    # 2. Any gemma4 model
    for tag in available_tags:
        if "gemma4" in tag.lower():
            return tag

    # 3. Any gemma model
    for tag in available_tags:
        if "gemma" in tag.lower():
            return tag

    # 4. Any lightweight/capable model
    for tag in available_tags:
        if any(preferred in tag.lower() for preferred in ["qwen3.5:4b", "qwen2.5-coder", "llama", "mistral"]):
            return tag

    # 5. First available model
    return available_tags[0]
