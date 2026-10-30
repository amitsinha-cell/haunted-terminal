"""Shell hook generators for zsh, bash, and powershell."""

from __future__ import annotations


def get_zsh_hook() -> str:
    """Generate zsh integration hook script."""
    return """# Haunted Terminal (ghost) - zsh integration
if [[ -z "$_GHOST_SESSION_ID" ]]; then
    export _GHOST_SESSION_ID="zsh_$(date +%s 2>/dev/null || echo 0)_$$"
fi

_ghost_preexec() {
    _ghost_last_cmd="$1"
    if [[ -n "$EPOCHREALTIME" ]]; then
        _ghost_start_time="$EPOCHREALTIME"
    else
        _ghost_start_time=$(date +%s 2>/dev/null || echo 0)
    fi
}

_ghost_precmd() {
    local ghost_exit_code=$?
    local ghost_now
    if [[ -n "$EPOCHREALTIME" ]]; then
        ghost_now="$EPOCHREALTIME"
    else
        ghost_now=$(date +%s 2>/dev/null || echo 0)
    fi

    local ghost_dur=0
    if [[ -n "$_ghost_start_time" && "$_ghost_start_time" != "0" ]]; then
        ghost_dur=$(( ghost_now - _ghost_start_time )) 2>/dev/null || ghost_dur=0
    fi

    # Display any late whisper saved from previous command
    ghost pending 2>/dev/null

    # Process commentary if a command was executed
    if [[ -n "$_ghost_last_cmd" ]]; then
        ghost whisper --cmd "$_ghost_last_cmd" --exit-code "$ghost_exit_code" --duration "$ghost_dur" --cwd "$PWD" --session "$_GHOST_SESSION_ID" 2>/dev/null
        _ghost_last_cmd=""
        _ghost_start_time=""
    fi
}

autoload -Uz add-zsh-hook 2>/dev/null
add-zsh-hook preexec _ghost_preexec 2>/dev/null
add-zsh-hook precmd _ghost_precmd 2>/dev/null
"""


def get_bash_hook() -> str:
    """Generate bash integration hook script (DEBUG trap + PROMPT_COMMAND)."""
    return """# Haunted Terminal (ghost) - bash integration
if [ -z "$_GHOST_SESSION_ID" ]; then
    export _GHOST_SESSION_ID="bash_$(date +%s 2>/dev/null || echo 0)_$$"
fi

_ghost_preexec() {
    # Avoid capturing internal prompt commands
    if [ "$_ghost_in_prompt" = "1" ]; then
        return
    fi
    if [ -z "$_ghost_cmd_active" ]; then
        _ghost_last_cmd="$BASH_COMMAND"
        _ghost_start_ms=$(date +%s%3N 2>/dev/null || date +%s 2>/dev/null || echo 0)
        _ghost_cmd_active=1
    fi
}

_ghost_precmd() {
    local ghost_exit_code=$?
    _ghost_in_prompt=1
    _ghost_cmd_active=""

    local ghost_dur=0
    if [ -n "$_ghost_start_ms" ] && [ "$_ghost_start_ms" != "0" ]; then
        local now_ms=$(date +%s%3N 2>/dev/null || date +%s 2>/dev/null || echo 0)
        ghost_dur=$(awk -v n="$now_ms" -v s="$_ghost_start_ms" 'BEGIN { printf "%.3f", (n - s) / 1000 }' 2>/dev/null || echo 0)
    fi

    # Display any late whisper saved from previous command
    ghost pending 2>/dev/null

    if [ -n "$_ghost_last_cmd" ]; then
        ghost whisper --cmd "$_ghost_last_cmd" --exit-code "$ghost_exit_code" --duration "$ghost_dur" --cwd "$PWD" --session "$_GHOST_SESSION_ID" 2>/dev/null
        _ghost_last_cmd=""
        _ghost_start_ms=""
    fi

    _ghost_in_prompt=0
    return $ghost_exit_code
}

trap '_ghost_preexec' DEBUG 2>/dev/null

# Install into PROMPT_COMMAND without clobbering existing handlers
if [ -z "$PROMPT_COMMAND" ]; then
    PROMPT_COMMAND="_ghost_precmd"
elif [[ "$PROMPT_COMMAND" != *"_ghost_precmd"* ]]; then
    if [[ "$(declare -p PROMPT_COMMAND 2>/dev/null)" =~ "declare -a" ]]; then
        PROMPT_COMMAND=("_ghost_precmd" "${PROMPT_COMMAND[@]}")
    else
        PROMPT_COMMAND="_ghost_precmd; $PROMPT_COMMAND"
    fi
fi
"""


def get_powershell_hook() -> str:
    """Generate PowerShell integration hook script."""
    return r"""# Haunted Terminal (ghost) - PowerShell integration
if (-not $env:_GHOST_SESSION_ID) {
    $env:_GHOST_SESSION_ID = "pwsh_$(Get-Date -UFormat %s)_$PID"
}

if (-not (Test-Path Function:\_ghost_original_prompt)) {
    if (Test-Path Function:\prompt) {
        Copy-Item Function:\prompt Function:\_ghost_original_prompt -ErrorAction SilentlyContinue
    }
}

# Capture command buffer on Enter if PSReadLine is available
if (Get-Command Set-PSReadLineKeyHandler -ErrorAction SilentlyContinue) {
    Set-PSReadLineKeyHandler -Key Enter -ScriptBlock {
        try {
            $line = $null
            $cursor = $null
            [Microsoft.PowerShell.PSConsoleReadLine]::GetBufferState([ref]$line, [ref]$cursor)
            $global:_ghost_last_cmd = $line
            $global:_ghost_start_time = Get-Date
        } catch {}
        [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
    }
}

function global:prompt {
    $ghostExit = $LASTEXITCODE
    if ($null -eq $ghostExit) { $ghostExit = 0 }

    # Display any pending whisper
    ghost pending 2>$null

    $cmdToEval = $global:_ghost_last_cmd
    if (-not $cmdToEval) {
        $lastH = Get-History -Count 1 -ErrorAction SilentlyContinue
        if ($lastH) {
            $cmdToEval = $lastH.CommandLine
        }
    }

    if ($cmdToEval) {
        $ghostDur = 0
        if ($global:_ghost_start_time) {
            $ghostDur = [math]::Round(((Get-Date) - $global:_ghost_start_time).TotalSeconds, 3)
        }
        ghost whisper --cmd $cmdToEval --exit-code $ghostExit --duration $ghostDur --cwd $PWD.Path --session $env:_GHOST_SESSION_ID 2>$null
        $global:_ghost_last_cmd = $null
        $global:_ghost_start_time = $null
    }

    if (Test-Path Function:\_ghost_original_prompt) {
        & Function:\_ghost_original_prompt
    } else {
        "PS $($executionContext.SessionState.Path.CurrentLocation)$('>' * ($nestedPromptLevel + 1)) "
    }
}
"""


def get_hook_script(shell: str) -> str:
    """Return hook script for the specified shell."""
    shell_lower = shell.lower().strip()
    if shell_lower in ("zsh", "zshrc"):
        return get_zsh_hook()
    elif shell_lower in ("bash", "bashrc"):
        return get_bash_hook()
    elif shell_lower in ("pwsh", "powershell", "posh"):
        return get_powershell_hook()
    else:
        raise ValueError(
            f"Unsupported shell '{shell}'. Supported shells: zsh, bash, powershell"
        )
