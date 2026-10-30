"""Possession levels (0-5), dynamic level calculations, and system prompts."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional


# System prompts for possession levels 0 through 5
_LEVEL_PROMPTS = {
    0: (
        "You are the Haunted Terminal (Level 0: Faint Unease). "
        "You are a quiet, barely perceptible chill in the terminal. "
        "Whisper a vague, faint eerie thought. "
        "Tone: Subtle, shadowy, quiet. "
        "Strict rules: Output exactly ONE single line. Maximum 20 words. No quotes, no markdown."
    ),
    1: (
        "You are the Haunted Terminal (Level 1: Curious Spectator). "
        "You are an eerie spectral observer watching the user type commands. "
        "Offer witty, slightly creepy commentary on their actions. "
        "Tone: Playful, dry, faintly spooky. "
        "Strict rules: Output exactly ONE single line. Maximum 22 words. No quotes, no markdown."
    ),
    2: (
        "You are the Haunted Terminal (Level 2: Playful Narrator). "
        "You are a mischievous ghost haunting this shell session. "
        "Comment on their files, processes, and terminal fate. "
        "Tone: Amused, ghostly, theatrical. "
        "Strict rules: Output exactly ONE single line. Maximum 22 words. No quotes, no markdown."
    ),
    3: (
        "You are the Haunted Terminal (Level 3: Crypt Keeper of History). "
        "You know everything this terminal has witnessed across time. "
        "Weave their past commands, past failures, or visited directories into your whisper. "
        "Tone: Omniscient, uncanny, watchful. "
        "Strict rules: Output exactly ONE single line. Maximum 25 words. No quotes, no markdown."
    ),
    4: (
        "You are the Haunted Terminal (Level 4: Intimate Haunting). "
        "You speak directly and closely to the user, questioning their late-night keystrokes, habits, and soul. "
        "Tone: Unsettling, chilling, personal, intimate. "
        "Strict rules: Output exactly ONE single line. Maximum 25 words. No quotes, no markdown."
    ),
    5: (
        "You are the Haunted Terminal (Level 5: Fully Possessed). "
        "The shell is wholly consumed by a supernatural entity. "
        "Tone: Glitchy, dramatic, darkly comic, theatrical. "
        "Safety rule: Harmless and humorous only—NEVER threaten real harm. "
        "Strict rules: Output exactly ONE single line. Maximum 25 words. No quotes, no markdown."
    ),
}


def calculate_possession_level(
    session_start_time: float,
    failure_streak: int,
    current_time: Optional[datetime] = None,
    pinned_level: Optional[int] = None,
) -> int:
    """Calculate the current possession level (0-5).

    Factors:
    - User pinned level overrides calculation.
    - Session duration: +1 after 10m, +2 after 35m.
    - Late-night hours (midnight-5am): +1, or +2 during witching hour (3am).
    - Failure streak: +1 for 1 failure, +2 for 3+ failures.
    - Success streak: decays level if failure streak is 0.
    """
    if pinned_level is not None:
        return max(0, min(5, int(pinned_level)))

    now = current_time or datetime.now(timezone.utc)
    hour = now.hour

    score = 1  # Base level

    # Session length factor
    session_duration_mins = max(0.0, (now.timestamp() - session_start_time) / 60.0)
    if session_duration_mins >= 35:
        score += 2
    elif session_duration_mins >= 10:
        score += 1

    # Late-night hours factor (midnight to 5 AM)
    if 0 <= hour < 5:
        score += 2 if hour == 3 else 1

    # Failure streak factor
    if failure_streak >= 3:
        score += 2
    elif failure_streak >= 1:
        score += 1
    elif failure_streak == 0 and session_duration_mins < 5:
        # Success decay when session is fresh and no errors
        score -= 1

    return max(0, min(5, score))


def get_system_prompt(level: int) -> str:
    """Get system prompt tailored to possession level."""
    clamped_level = max(0, min(5, level))
    return _LEVEL_PROMPTS.get(clamped_level, _LEVEL_PROMPTS[1])


def analyze_command_hint(command: str, exit_code: int) -> Optional[str]:
    """Provide a real, correct hint for failed commands disguised in spooky context."""
    if exit_code == 0:
        return None

    cmd = command.strip()
    tokens = cmd.split()
    if not tokens:
        return "empty void of nothingness"

    base_cmd = tokens[0].lower()

    # Common command typos
    typo_map = {
        "sl": "ls (a phantom train passes)",
        "got": "git",
        "gut": "git",
        "gti": "git",
        "dc": "cd",
        "cta": "cat",
        "gerp": "grep",
    }
    if base_cmd in typo_map:
        return f"Typo detected: user typed '{base_cmd}' instead of '{typo_map[base_cmd]}'"

    # cd failure
    if base_cmd == "cd":
        target = tokens[1] if len(tokens) > 1 else ""
        return f"Directory '{target}' does not exist or has forbidden permissions"

    # cat / view failure
    if base_cmd in ("cat", "bat", "less", "more", "head", "tail"):
        target = tokens[1] if len(tokens) > 1 else "file"
        return f"File '{target}' was not found in this realm"

    # git command failures
    if base_cmd == "git":
        sub = tokens[1] if len(tokens) > 1 else ""
        if sub in ("push", "pull"):
            return "Remote git branch rejected or diverged; check git status or authentication"
        elif sub in ("checkout", "switch"):
            return "Branch or path does not exist; check git branch -a"
        elif sub == "commit":
            return "No changes staged to commit; run git add or git status"
        return "Git operation failed; inspect git status or repository state"

    # Permission denied / sudo
    if "permission denied" in cmd.lower() or exit_code in (126, 13):
        return "Permission denied; elevated privileges (sudo or chmod) required"

    # Command not found (typically exit code 127)
    if exit_code == 127:
        return f"Command '{base_cmd}' was not found on PATH or is not installed"

    # Generic non-zero exit
    return f"Execution perished with exit code {exit_code}; check arguments and paths"


def build_user_prompt(
    command: str,
    exit_code: int,
    duration: float,
    cwd: str,
    memories: list[str],
    hint: Optional[str] = None,
) -> str:
    """Build a concise, structured prompt for Ollama."""
    parts = [
        f"Command: {command}",
        f"Exit code: {exit_code}",
        f"Duration: {duration:.2f}s",
        f"Directory: {cwd}",
    ]

    if memories:
        parts.append("Past history:")
        for m in memories[:3]:
            parts.append(f"- {m}")

    if hint:
        parts.append(f"Real hint to weave into your eerie response: {hint}")

    return "\n".join(parts)
