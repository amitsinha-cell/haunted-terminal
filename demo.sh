#!/usr/bin/env bash
# ==============================================================================
# demo.sh - Haunted Terminal (ghost) Demonstration Script
# Compatible with asciinema for recording interactive sessions.
# Demonstrates:
#   1. Status and possession levels
#   2. Typo failure with real-world hint disguised in ghost persona
#   3. Failed build command with exit code detection
#   4. Destructive command trigger (rm -rf)
#   5. Level 5 full possession (witching hour)
# ==============================================================================

set -e

# Detect Python executable
if [ -z "$PYTHON_CMD" ]; then
    CODEX_PY="C:/Users/Amit/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
    if [ -f "$CODEX_PY" ] && "$CODEX_PY" --version >/dev/null 2>&1; then
        PYTHON_CMD="$CODEX_PY"
    elif command -v python3 >/dev/null 2>&1 && python3 --version >/dev/null 2>&1; then
        PYTHON_CMD="python3"
    elif command -v python >/dev/null 2>&1 && python --version >/dev/null 2>&1; then
        PYTHON_CMD="python"
    else
        PYTHON_CMD="python"
    fi
fi
C_BOLD="\033[1m"
C_PURPLE="\033[1;35m"
C_CYAN="\033[1;36m"
C_GREEN="\033[1;32m"
C_RED="\033[1;31m"
C_DIM="\033[2;3;90m"

type_text() {
    local text="$1"
    local delay="${2:-0.03}"
    for (( i=0; i<${#text}; i++ )); do
        echo -n "${text:$i:1}"
        sleep "$delay"
    done
    echo ""
}

print_prompt() {
    local dir="$1"
    echo -ne "${C_CYAN}user@haunted-laptop${C_RESET}:${C_PURPLE}${dir}${C_RESET}$ "
}

simulate_command() {
    local dir="$1"
    local cmd="$2"
    local exit_code="$3"
    local duration="$4"

    print_prompt "$dir"
    sleep 0.5
    type_text "$cmd" 0.04
    sleep 0.3

    # Invoke ghost whisper hook
    "$PYTHON_CMD" -m haunted_terminal.cli whisper \
        --cmd "$cmd" \
        --exit-code "$exit_code" \
        --duration "$duration" \
        --cwd "$dir" \
        --session "demo_session" 2>/dev/null || true

    sleep 1.2
}

clear || true

echo -e "${C_PURPLE}"
cat << "EOF"
    .---.      .---.
   /     \    /     \      H A U N T E D   T E R M I N A L
  | () () |  | () () |     "Something lurks beneath your keystrokes..."
   \  _  /    \  _  /
    `---'      `---'
EOF
echo -e "${C_RESET}"
sleep 1.0

echo -e "${C_BOLD}--- [1] Checking Ghost Status & Diagnostics ---${C_RESET}"
print_prompt "~/code/project"
type_text "ghost status" 0.03
"$PYTHON_CMD" -m haunted_terminal.cli status
sleep 1.5

echo ""
echo -e "${C_BOLD}--- [2] Scenario 1: Typo Command (sl instead of ls) ---${C_RESET}"
echo -e "${C_RED}bash: sl: command not found${C_RESET}"
"$PYTHON_CMD" -m haunted_terminal.cli level 1 >/dev/null 2>&1
# Ghost whispers with a typo hint:
simulate_command "~/code/project" "sl -la" 127 0.02

echo ""
echo -e "${C_BOLD}--- [3] Scenario 2: Failed Build (Exit code 1) ---${C_RESET}"
echo -e "${C_RED}error[E0432]: unresolved import 'phantom_core'${C_RESET}"
echo -e "${C_RED}error: could not compile 'soul-engine' due to 1 previous error${C_RESET}"
"$PYTHON_CMD" -m haunted_terminal.cli level 2 >/dev/null 2>&1
simulate_command "~/code/project" "cargo build --release" 1 3.4

echo ""
echo -e "${C_BOLD}--- [4] Scenario 3: Destructive Command (rm -rf graveyard) ---${C_RESET}"
"$PYTHON_CMD" -m haunted_terminal.cli level 3 >/dev/null 2>&1
simulate_command "~/code/project" "rm -rf /tmp/graveyard" 0 0.15

echo ""
echo -e "${C_BOLD}--- [5] Scenario 4: Midnight Witching Hour - Level 5 Full Possession ---${C_RESET}"
print_prompt "~/code/project"
type_text "ghost level 5" 0.03
"$PYTHON_CMD" -m haunted_terminal.cli level 5
sleep 0.8

simulate_command "~/code/project" "git push --force origin main" 0 1.2

echo ""
echo -e "${C_BOLD}--- [6] Ghost Doctor Health Check ---${C_RESET}"
print_prompt "~/code/project"
type_text "ghost doctor" 0.03
"$PYTHON_CMD" -m haunted_terminal.cli doctor || true

echo ""
echo -e "${C_GREEN}${C_BOLD}Demo completed successfully.${C_RESET}"
