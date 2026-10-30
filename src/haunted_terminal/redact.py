"""Secret redaction and output sanitization for Haunted Terminal.

Ensures that no passwords, API keys, tokens, or private credentials
reach the local model or the SQLite database.
"""

from __future__ import annotations

import re

# Compiled regex patterns for redaction
_PATTERNS = [
    # Private keys (PEM format)
    (
        re.compile(
            r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----",
            re.MULTILINE,
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    # JWT tokens
    (
        re.compile(
            r"\beyJ[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]{10,}\b"
        ),
        "[REDACTED_JWT]",
    ),
    # AWS access key ID
    (
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[REDACTED_AWS_KEY]",
    ),
    # GitHub personal access / app tokens
    (
        re.compile(
            r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}\b"
        ),
        "[REDACTED_GITHUB_TOKEN]",
    ),
    # OpenAI API keys
    (
        re.compile(r"\bsk-(?:proj-|none-)?[A-Za-z0-9_\-]{20,}\b"),
        "[REDACTED_OPENAI_KEY]",
    ),
    # Google Cloud / Firebase API key
    (
        re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"),
        "[REDACTED_GOOGLE_KEY]",
    ),
    # Slack tokens
    (
        re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}\b"),
        "[REDACTED_SLACK_TOKEN]",
    ),
    # URL credentials (http://user:password@host)
    (
        re.compile(r"(https?://)([^:\s/@]+):([^@\s/]+)@"),
        r"\1\2:[REDACTED]@",
    ),
    # Authorization header
    (
        re.compile(
            r"(?i)(Authorization:\s*(?:Bearer|Basic)\s+)([^\s\"',;]+)"
        ),
        r"\1[REDACTED]",
    ),
    # Shell export commands: export FOO=secret or export FOO="secret"
    (
        re.compile(
            r"(export\s+[A-Za-z_][A-Za-z0-9_]*=)(?:\"[^\"]*\"|'[^']*'|[^\s;&|]+)"
        ),
        r"\1[REDACTED]",
    ),
    # Environment variables with sensitive names: API_KEY=xyz, PASSWORD=xyz
    (
        re.compile(
            r"(?i)\b([A-Za-z0-9_]*(?:TOKEN|KEY|SECRET|PASSWORD|PASSWD|AUTH|CREDENTIAL)[A-Za-z0-9_]*=)(?:\"[^\"]*\"|'[^']*'|[^\s;&|]+)"
        ),
        r"\1[REDACTED]",
    ),
    # CLI options: --password foo, -p foo, --token=foo, --api-key foo
    (
        re.compile(
            r"(?i)(--(?:password|passwd|token|api-key|apikey|secret|auth)[=\s])(?:\"[^\"]*\"|'[^']*'|[^\s;&|]+)"
        ),
        r"\1[REDACTED]",
    ),
    # Query parameters / key-value assignments
    (
        re.compile(
            r"(?i)\b((?:token|api_key|apikey|access_token|client_secret|passwd|password)=)(?:\"[^\"]*\"|'[^']*'|[^\s&;]+)"
        ),
        r"\1[REDACTED]",
    ),
]

# ANSI escape sequence stripper
_ANSI_STRIPPER = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Thinking tags stripper for reasoning models
_THINKING_STRIPPER = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)


def redact_secrets(text: str) -> str:
    """Redact passwords, tokens, API keys, and sensitive flags from text.

    Args:
        text: Raw input string (e.g. terminal command).

    Returns:
        String with all detected secrets replaced by [REDACTED].
    """
    if not text:
        return ""

    redacted = text
    for pattern, replacement in _PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def has_secrets(text: str) -> bool:
    """Check if the text contains any secret matching our patterns."""
    if not text:
        return False
    return any(pattern.search(text) is not None for pattern, _ in _PATTERNS)


def sanitize_model_output(text: str, max_words: int = 25) -> str:
    """Sanitize and constrain the model output to a safe, clean, single line.

    Strips control characters, ANSI escape sequences, markdown fences,
    model reasoning/thinking tags, and truncates to ~25 words.

    Args:
        text: Raw output string from LLM.
        max_words: Maximum number of words allowed (default 25).

    Returns:
        Clean single-line string.
    """
    if not text:
        return ""

    # Remove reasoning/thinking tags
    cleaned = _THINKING_STRIPPER.sub("", text)

    # Strip ANSI escape sequences
    cleaned = _ANSI_STRIPPER.sub("", cleaned)

    # Remove markdown code fences or backticks
    cleaned = re.sub(r"```[\w]*\n?", "", cleaned)
    cleaned = cleaned.replace("```", "").replace("`", "")

    # Convert tabs, newlines, and carriage returns to space
    cleaned = re.sub(r"[\r\n\t]+", " ", cleaned)

    # Strip non-printable control characters (ASCII < 32)
    cleaned = "".join(ch for ch in cleaned if ord(ch) >= 32)

    # Collapse multiple spaces and newlines into a single space
    cleaned = " ".join(cleaned.split())

    # Strip surrounding quotes if the model wrapped output in quotes
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        cleaned = cleaned[1:-1].strip()

    # Limit to max_words
    words = cleaned.split()
    if len(words) > max_words:
        cleaned = " ".join(words[:max_words]).rstrip(",;:-") + "..."

    return cleaned.strip()
