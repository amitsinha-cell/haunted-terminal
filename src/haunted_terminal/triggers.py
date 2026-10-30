"""Trigger evaluation logic for Haunted Terminal.

Determines whether the ghost whispers after a given command.
"""

from __future__ import annotations

import random
import re
from typing import Optional

# Pre-compiled regex patterns for always-on triggers
_SUDO_PATTERN = re.compile(r"(?:^|[|;&]\s*)sudo\b")
_RM_DESTRUCTIVE_PATTERN = re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\b|\brm\s+-[a-zA-Z]*f[a-zA-Z]*r\b|\brm\s+-r\b|\brmdir\b")
_GIT_FORCE_PATTERN = re.compile(r"\bgit\s+push\b.*?(?:--force|-f\b)")
_GIT_RESET_HARD_PATTERN = re.compile(r"\bgit\s+reset\b.*?--hard\b")

# Probability scaling by possession level [0, 5]
_PROBABILITY_BY_LEVEL = {
    0: 0.06,   # ~1 in 16
    1: 0.10,   # ~1 in 10
    2: 0.125,  # ~1 in 8 (base)
    3: 0.18,   # ~1 in 5.5
    4: 0.25,   # ~1 in 4
    5: 0.40,   # ~1 in 2.5
}


def should_trigger(
    command: str,
    exit_code: int,
    duration: float = 0.0,
    idle_time: float = 0.0,
    days_since_dir_visit: Optional[float] = None,
    level: int = 1,
    random_roll: Optional[float] = None,
) -> tuple[bool, str]:
    """Determine if ghost should whisper after command execution.

    Args:
        command: Redacted command string.
        exit_code: Process exit code.
        duration: Command execution duration in seconds.
        idle_time: Seconds elapsed since previous command in this terminal.
        days_since_dir_visit: Days since this directory was last visited, if known.
        level: Current possession level (0-5).
        random_roll: Optional float [0, 1) for deterministic testing.

    Returns:
        tuple of (should_whisper, reason_description)
    """
    cmd = command.strip()

    # 1. Non-zero exit code
    if exit_code != 0:
        return True, f"non-zero exit code ({exit_code})"

    # 2. sudo invocation
    if _SUDO_PATTERN.search(cmd):
        return True, "sudo invocation"

    # 3. Destructive rm commands (rm -rf, rm -fr, rm -r, rmdir)
    if _RM_DESTRUCTIVE_PATTERN.search(cmd):
        return True, "destructive removal command"

    # 4. git push --force / git push -f
    if _GIT_FORCE_PATTERN.search(cmd):
        return True, "forceful git push"

    # 5. git reset --hard
    if _GIT_RESET_HARD_PATTERN.search(cmd):
        return True, "git reset hard"

    # 6. Long-running command (> 30s)
    if duration > 30.0:
        return True, f"long duration ({duration:.1f}s)"

    # 7. First command after 30+ minutes idle (> 1800s)
    if idle_time > 1800.0:
        return True, f"idle awakening ({idle_time/60.0:.1f} mins idle)"

    # 8. cd into directory not visited in 30+ days
    if days_since_dir_visit is not None and days_since_dir_visit > 30.0:
        return True, f"long-forgotten directory ({days_since_dir_visit:.1f} days)"

    # 9. Otherwise, probabilistic trigger scaled by possession level (~1 in 8 base)
    prob = _PROBABILITY_BY_LEVEL.get(max(0, min(5, level)), 0.125)
    roll = random.random() if random_roll is None else random_roll

    if roll < prob:
        return True, f"possession chance (level {level}, p={prob:.2f})"

    return False, "quiet"
