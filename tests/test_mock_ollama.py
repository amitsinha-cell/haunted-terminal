"""Unit tests with a mock Ollama HTTP server for fallbacks and timeouts."""

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Generator
import pytest

from haunted_terminal.config import GhostConfig
from haunted_terminal.ollama import (
    call_whisper_model,
    check_ollama_status,
    format_whisper,
)


class MockOllamaHandler(BaseHTTPRequestHandler):
    """Mock handler simulating Ollama API endpoints."""

    def log_message(self, format, *args):
        # Silence HTTP server logs during test runs
        pass

    def do_GET(self):
        if self.path == "/api/tags":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {
                "models": [
                    {"name": "gemma4:e4b", "model": "gemma4:e4b"},
                    {"name": "qwen2.5-coder:7b", "model": "qwen2.5-coder:7b"},
                ]
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        payload = json.loads(body)

        if self.path == "/api/chat":
            # Simulate slow response for timeout testing
            if payload.get("model") == "slow-timeout-model":
                time.sleep(1.0)

            # Simulate error model
            if payload.get("model") == "failing-model":
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b'{"error": "model crashed"}')
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "model": payload.get("model", "gemma4:e4b"),
                "message": {
                    "role": "assistant",
                    "content": "The shadows watch every keystroke you make.",
                },
                "done": True,
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def mock_ollama_server() -> Generator[str, None, None]:
    port = get_free_port()
    server = HTTPServer(("127.0.0.1", port), MockOllamaHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


def test_mock_ollama_status_success(mock_ollama_server: str):
    connected, err, models = check_ollama_status(mock_ollama_server, timeout=1.0)
    assert connected
    assert not err
    assert "gemma4:e4b" in models
    assert "qwen2.5-coder:7b" in models


def test_mock_ollama_chat_success(mock_ollama_server: str):
    cfg = GhostConfig(
        ollama_host=mock_ollama_server,
        model="gemma4:e4b",
        timeout=1.5,
    )
    whisper = call_whisper_model(
        system_prompt="You are a ghost.",
        user_prompt="Command: ls",
        config=cfg,
    )
    assert whisper is not None
    assert "shadows watch" in whisper


def test_mock_ollama_timeout_fallback(mock_ollama_server: str):
    cfg = GhostConfig(
        ollama_host=mock_ollama_server,
        model="slow-timeout-model",
        timeout=0.1,  # Strict short timeout
    )
    whisper = call_whisper_model(
        system_prompt="You are a ghost.",
        user_prompt="Command: ls",
        config=cfg,
    )
    # Must fail silently and return None
    assert whisper is None


def test_mock_ollama_error_fallback(mock_ollama_server: str):
    cfg = GhostConfig(
        ollama_host=mock_ollama_server,
        model="failing-model",
        timeout=1.0,
    )
    whisper = call_whisper_model(
        system_prompt="You are a ghost.",
        user_prompt="Command: ls",
        config=cfg,
    )
    # Must fail silently on HTTP 500
    assert whisper is None


def test_mock_ollama_connection_refused():
    cfg = GhostConfig(
        ollama_host="http://127.0.0.1:59999",  # Unused port
        model="gemma4:e4b",
        timeout=0.5,
    )
    whisper = call_whisper_model(
        system_prompt="You are a ghost.",
        user_prompt="Command: ls",
        config=cfg,
    )
    assert whisper is None

    connected, err, models = check_ollama_status("http://127.0.0.1:59999", timeout=0.5)
    assert not connected
    assert "Could not connect" in err or "timed out" in err


def test_format_whisper():
    formatted = format_whisper("Beware the void")
    assert "\033[2;3;90m" in formatted
    assert "👻 Beware the void" in formatted
    assert "\033[0m" in formatted
