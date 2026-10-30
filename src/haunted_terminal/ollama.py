"""Ollama client and communication for Haunted Terminal."""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx

from haunted_terminal.config import GhostConfig
from haunted_terminal.redact import sanitize_model_output


def format_whisper(text: str) -> str:
    """Format whisper with dim, italic ANSI gray styling."""
    return f"\033[2;3;90m👻 {text}\033[0m"


def check_ollama_status(
    host: str = "http://localhost:11434", timeout: float = 1.0
) -> tuple[bool, str, list[str]]:
    """Check connectivity to Ollama and return available model tags.

    Returns:
        (is_connected, error_message, list_of_models)
    """
    url = f"{host.rstrip('/')}/api/tags"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                models = [
                    m.get("name") or m.get("model")
                    for m in data.get("models", [])
                    if m.get("name") or m.get("model")
                ]
                return True, "", models
            return False, f"Ollama returned HTTP {resp.status_code}", []
    except httpx.ConnectError:
        return False, f"Could not connect to Ollama at {host}. Is ollama running?", []
    except httpx.TimeoutException:
        return False, f"Connection to Ollama at {host} timed out after {timeout}s", []
    except Exception as e:
        return False, str(e), []


def call_whisper_model(
    system_prompt: str,
    user_prompt: str,
    config: GhostConfig,
    timeout: Optional[float] = None,
) -> Optional[str]:
    """Call Ollama /api/chat with strict timeout and keep_alive.

    Returns sanitized, single-line whisper, or None if unavailable/timed out.
    """
    call_timeout = timeout if timeout is not None else config.timeout
    url = f"{config.ollama_host.rstrip('/')}/api/chat"

    payload: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "num_predict": config.num_predict,
            "num_ctx": config.num_ctx,
            "temperature": config.temperature,
        },
        "keep_alive": config.keep_alive,
    }

    try:
        with httpx.Client(timeout=call_timeout) as client:
            resp = client.post(url, json=payload)
            if resp.status_code != 200:
                return None

            data = resp.json()
            msg = data.get("message", {})
            content = msg.get("content", "")

            # Fallback if reasoning model consumed tokens in thinking field
            if not content and "thinking" in msg:
                content = msg["thinking"]

            if not content:
                return None

            sanitized = sanitize_model_output(content, max_words=25)
            return sanitized if sanitized else None

    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError):
        # Silently fail on network/timeout error
        return None
    except Exception:
        return None
