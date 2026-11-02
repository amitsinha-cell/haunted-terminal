# 👻 Haunted Terminal (`ghost`)

> *A local LLM whispers short, eerie, in-character commentary after commands you run in your terminal.*

[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Ollama](https://img.shields.io/badge/backend-Ollama-black.svg)](https://ollama.com/)
[![Tests](https://img.shields.io/badge/tests-50%20passing-brightgreen.svg)]()

---

## 📽️ Demo

```
    .---.      .---.
   /     \    /     \      H A U N T E D   T E R M I N A L
  | () () |  | () () |     "Something lurks beneath your keystrokes..."
   \  _  /    \  _  /
    `---'      `---'

user@haunted-laptop:~/code/project$ sl -la
bash: sl: command not found
👻 The phantom train chugs into the void; you typed 'sl' instead of 'ls'...

user@haunted-laptop:~/code/project$ cargo build --release
error[E0432]: unresolved import 'phantom_core'
error: could not compile 'soul-engine' due to 1 previous error
👻 Missing import 'phantom_core'... your binary perished into cold digital dust.

user@haunted-laptop:~/code/project$ rm -rf /tmp/graveyard
👻 The graveyard was wiped from reality. Not even a trace remains.
```

---

## 🌟 Why Open Source AI Matters Here

Using a local LLM for shell integration isn't just a technical preference—it is fundamentally necessary for this kind of tool:

1. **Your Shell History Stays on Your Machine**:
   Terminal commands frequently contain sensitive paths, internal project names, repository URLs, and environment variables. Sending every command you run to an external cloud API is a severe security and privacy hazard. With **Ollama running locally**, your shell history never leaves your RAM and SSD.
2. **True Offline Operation**:
   Whether you're developing on a plane, riding a subway, or in an air-gapped lab, your ghost whispers without needing an active internet connection.
3. **Model Swappability & Custom Personas**:
   Swap models instantly based on your hardware. Run an ultra-lightweight 2B model for sub-200ms latency, a balanced 4B model, or a fine-tuned spooky persona.
4. **Zero Marginal Cost**:
   Developers run hundreds of shell commands daily. Cloud APIs would charge per invocation or hit rate limits; local inference on your GPU is completely free and unlimited.

---

## ⚡ Whisper Latency on NVIDIA RTX 4050 Laptop (6GB VRAM)

Tested locally via Ollama with `num_ctx 1024`, `num_predict 40`, and `keep_alive 30m` on an RTX 4050 Laptop GPU (6GB VRAM):

| Model | Parameters | Quantization | VRAM Offload | Warm Prompt Eval | Warm Token Gen | Total Whisper Latency | Prompt Impact |
|---|---|---|---|---|---|---|---|
| **Gemma 4 E2B** | 2.3B | Q4_K_M | 100% GPU (2.8 GB) | ~35 ms | ~82 tok/s | **~190 ms - 260 ms** | **0 ms** (Non-blocking) |
| **Gemma 4 E4B** | 4.2B | Q4_K_M | 100% GPU (4.2 GB) | ~65 ms | ~58 tok/s | **~380 ms - 520 ms** | **0 ms** (Non-blocking) |
| **Qwen 3.5 4B** | 4.2B | Q4_K_M | 100% GPU (3.3 GB) | ~80 ms | ~52 tok/s | **~410 ms - 580 ms** | **0 ms** (Non-blocking) |
| **Qwen 2.5 Coder 7B**| 7.6B | Q4_K_M | Partial / CPU (4.7 GB)| ~140 ms | ~18 tok/s | **~1200 ms - 1800 ms**| **0 ms** (Saved for next prompt) |

> **Hard 1.5s Timeout Guarantee**: The prompt is **never blocked**. If an LLM call exceeds the synchronous budget (~0.8s) or is cold loading, the whisper is detached to the background and displayed cleanly at the **very next prompt**. When ghost decides not to speak, the hook overhead is **<15ms**.

---

## 🔮 Core Features

- **Six Possession Levels (0 - 5)**:
  - **Level 0 (Faint Unease)**: Subtle, vague, shadows in the terminal.
  - **Level 1-2 (Playful Narrator)**: Witty, amused spectral observer.
  - **Level 3 (Crypt Keeper)**: Accesses your SQLite command history (`~/.local/share/ghost/history.db`).
  - **Level 4 (Intimate Haunting)**: Addresses you directly, questioning late-night keystrokes.
  - **Level 5 (Fully Possessed)**: Manic, glitchy, theatrical terminal possession (harmless and darkly funny; never threatening real harm).
- **Dynamic Possession Mechanics**:
  - Possession rises with session length, late-night hours (**midnight to 5 AM / 3 AM witching hour**), and consecutive failed commands.
  - Possession decays on successful commands.
  - Can be pinned manually with `ghost level N` or set back to dynamic with `ghost level auto`.
- **Real Hints Inside Spooky Whispers**:
  - Failed commands (exit code $\ne$ 0) trigger actionable, correct hints (e.g. typos like `sl` vs `ls`, missing file paths, git divergence, permission issues) cloaked in the ghost persona.
- **SQLite Long-Term Memory**:
  - Stores commands, exit codes, durations, working directories, and timestamps.
  - Pulls up to 3 relevant past events when commenting ("*You ran this at 2:13 AM last Tuesday and it failed...*").
- **Strict Privacy & Secret Redaction**:
  - Automatic redaction of API keys (AWS, OpenAI, GitHub, Google, Slack), JWTs, passwords, private keys, `export VAR=...`, and Authorization headers *before* reaching the model or database.
- **Non-Repeating Whispers**:
  - Guarantees whispers are not repeated within a session.

---

## 🚀 Installation & Quickstart

### 1. Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com/) running locally:
  ```bash
  ollama serve
  ollama pull gemma4:e4b   # or: ollama pull qwen3.5:4b
  ```

### 2. Install Haunted Terminal
Using `pipx` (recommended):
```bash
pipx install .
```
Or via standard `pip`:
```bash
pip install -e .
```

### 3. Activate in Your Shell

#### Option A: One-Command Auto-Install
```bash
ghost install bash    # for ~/.bashrc
ghost install zsh     # for ~/.zshrc
ghost install pwsh    # for PowerShell profile
```
*(Creates an automatic `.bak` backup before editing)*

#### Option B: Manual Shell Init
Add the eval hook to your configuration file:

- **Zsh** (`~/.zshrc`):
  ```zsh
  eval "$(ghost init zsh)"
  ```

- **Bash** (`~/.bashrc`):
  ```bash
  eval "$(ghost init bash)"
  ```

- **PowerShell** (`$PROFILE`):
  ```powershell
  Invoke-Expression (& ghost init powershell | Out-String)
  ```

Reload your shell or run `source ~/.bashrc`.

---

## 🛠️ CLI Reference

| Command | Description |
|---|---|
| `ghost status` | View current status, active model, possession level, streak, and history counts. |
| `ghost doctor` | Run comprehensive health check: Ollama connection, model availability, latency test, database health. |
| `ghost on` | Enable ghost commentary. |
| `ghost off` | Silence ghost commentary (ghost sleeps). |
| `ghost level [N]` | View current level, pin level to `N` (0-5), or unpin with `ghost level auto`. |
| `ghost init <shell>` | Output shell hook script for `zsh`, `bash`, or `powershell`. |
| `ghost install [shell]`| Safely append hook code to your shell's rc file with backup. |
| `ghost exorcise` | Remove shell hooks from all rc files. |
| `ghost exorcise --all` | Remove shell hooks and completely purge SQLite history and config. |

---

## ⚙️ Configuration

Haunted Terminal can be configured via environment variables or `~/.config/ghost/config.json`:

| Environment Variable | Config Key | Default | Description |
|---|---|---|---|
| `GHOST_MODEL` | `model` | Auto-detected | LLM model tag in Ollama (e.g. `gemma4:e4b`) |
| `OLLAMA_HOST` | `ollama_host` | `http://localhost:11434` | Ollama URL (useful for WSL2 users) |
| `GHOST_TIMEOUT` | `timeout` | `1.5` | Hard timeout in seconds for LLM call |
| `GHOST_SYNC_TIMEOUT`| `sync_timeout`| `0.8` | Max synchronous wait before detaching to background |
| `GHOST_DISABLED` | `enabled` | `0` | Set to `1` to temporarily disable |

Example `~/.config/ghost/config.json`:
```json
{
  "ollama_host": "http://localhost:11434",
  "model": "gemma4:e4b",
  "timeout": 1.5,
  "sync_timeout": 0.8,
  "keep_alive": "30m",
  "num_predict": 40,
  "num_ctx": 1024,
  "temperature": 0.7
}
```

---

## 🧪 Running Tests

The test suite covers secret redaction, trigger rules, possession level dynamics, SQLite persistence, and mock Ollama HTTP server failure fallbacks:

```bash
pytest -v
```

---

## 📜 License

MIT License. See [LICENSE](LICENSE) for details.
