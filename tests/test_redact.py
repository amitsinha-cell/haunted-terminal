"""Unit tests for secret redaction and output sanitization."""

import pytest
from haunted_terminal.redact import (
    has_secrets,
    redact_secrets,
    sanitize_model_output,
)


def test_redact_export():
    raw = "export GITHUB_TOKEN=ghp_1234567890abcdefghijklmnopqrstuvwxyz1234"
    redacted = redact_secrets(raw)
    assert "ghp_" not in redacted
    assert "[REDACTED]" in redacted or "[REDACTED_GITHUB_TOKEN]" in redacted


def test_redact_aws_key():
    raw = "aws s3 ls --profile default --key AKIAIOSFODNN7EXAMPLE"
    redacted = redact_secrets(raw)
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert "[REDACTED_AWS_KEY]" in redacted


def test_redact_openai_key():
    raw = "curl https://api.openai.com -H 'Authorization: Bearer sk-1234567890abcdefghijklmnopqrstuvwxyz'"
    redacted = redact_secrets(raw)
    assert "sk-" not in redacted
    assert "[REDACTED" in redacted


def test_redact_google_key():
    raw = "curl 'https://maps.googleapis.com/maps/api/geocode/json?key=AIzaSyA1234567890abcdefghijklmnopqrstuvw'"
    redacted = redact_secrets(raw)
    assert "AIzaSy" not in redacted
    assert "[REDACTED" in redacted


def test_redact_inline_password():
    raw = "mysql -u root --password secretpass123 -h localhost db"
    redacted = redact_secrets(raw)
    assert "secretpass123" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_url_credentials():
    raw = "git clone https://username:supersecretpassword@github.com/org/repo.git"
    redacted = redact_secrets(raw)
    assert "supersecretpassword" not in redacted
    assert "username:[REDACTED]@" in redacted


def test_has_secrets():
    assert has_secrets("export TOKEN=abcdef123456")
    assert has_secrets("curl -H 'Authorization: Bearer token123'")
    assert not has_secrets("ls -la /var/log")
    assert not has_secrets("git status")


def test_sanitize_model_output_ansi():
    raw = "\x1b[31;1mBeware\x1b[0m the shadows of \x1b[32mcode\x1b[0m"
    sanitized = sanitize_model_output(raw)
    assert "\x1b" not in sanitized
    assert sanitized == "Beware the shadows of code"


def test_sanitize_model_output_newlines_and_quotes():
    raw = '  "The void stirs.\n\nIt notices your commands."  '
    sanitized = sanitize_model_output(raw)
    assert sanitized == "The void stirs. It notices your commands."


def test_sanitize_model_output_thinking_tags():
    raw = "<think>The user ran git status. I will say something spooky.</think>The branches reach for you in silence."
    sanitized = sanitize_model_output(raw)
    assert "<think>" not in sanitized
    assert "The branches reach for you in silence." in sanitized


def test_sanitize_model_output_word_limit():
    long_raw = "word " * 40
    sanitized = sanitize_model_output(long_raw, max_words=20)
    words = sanitized.replace("...", "").split()
    assert len(words) == 20
    assert sanitized.endswith("...")
