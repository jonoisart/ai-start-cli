# Standalone `~/bin/ai` script version.
# The script below is zsh-optimized for macOS. Bash version in future features.

## Create the Script

```bash
mkdir -p ~/bin
cat > ~/bin/ai << 'EOF'
#!/bin/zsh

# AI Model Launcher
# Usage: ai <command> [args]

set -e

# Model definitions
typeset -A MODELS
typeset -A MODEL_NAMES

MODELS=(
    qwen "/Users/onoi/.cache/huggingface/hub/models--HauhauCS--Qwen3.5-9B-Uncensored-HauhauCS-Aggressive/snapshots/335e9ef38ada3edf9f9a3a6c2836022c1ab76ea1/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q8_0.gguf"
    qwen35 "/Users/onoi/.cache/huggingface/hub/models--HauhauCS--Qwen3.5-9B-Uncensored-HauhauCS-Aggressive/snapshots/335e9ef38ada3edf9f9a3a6c2836022c1ab76ea1/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q8_0.gguf"
    qwen3.5 "/Users/onoi/.cache/huggingface/hub/models--HauhauCS--Qwen3.5-9B-Uncensored-HauhauCS-Aggressive/snapshots/335e9ef38ada3edf9f9a3a6c2836022c1ab76ea1/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q8_0.gguf"
    gemma "/Users/onoi/.cache/huggingface/hub/models--HauhauCS--Gemma-4-E4B-Uncensored-HauhauCS-Aggressive/snapshots/45b6a334b4bcd1d7f37179df58b3b1d66a184e5d/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf"
    gemma4 "/Users/onoi/.cache/huggingface/hub/models--HauhauCS--Gemma-4-E4B-Uncensored-HauhauCS-Aggressive/snapshots/45b6a334b4bcd1d7f37179df58b3b1d66a184e5d/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf"
    gemma-base "/Users/onoi/.cache/huggingface/hub/models--unsloth--gemma-4-E4B-it-GGUF/snapshots/315e03409eb1cdde302488d66e586dea1e82aad1/gemma-4-E4B-it-Q8_0.gguf"
    gemma-instruct "/Users/onoi/.cache/huggingface/hub/models--unsloth--gemma-4-E4B-it-GGUF/snapshots/315e03409eb1cdde302488d66e586dea1e82aad1/gemma-4-E4B-it-Q8_0.gguf"
)

MODEL_NAMES=(
    qwen "Qwen 3.5 9B Uncensored (Q8_0)"
    qwen35 "Qwen 3.5 9B Uncensored (Q8_0)"
    qwen3.5 "Qwen 3.5 9B Uncensored (Q8_0)"
    gemma "Gemma 4 Uncensored (Q4_K_M)"
    gemma4 "Gemma 4 Uncensored (Q4_K_M)"
    gemma-base "Gemma 4 Instruct (Q8_0)"
    gemma-instruct "Gemma 4 Instruct (Q8_0)"
)

# Default settings
DEFAULT_PORT=8083
DEFAULT_CTX=131072
DEFAULT_TEMP=0.7
DEFAULT_TOP_P=0.8
DEFAULT_TOP_K=20

# Help
show_help() {
    cat << 'HELP'
Usage: ai <command> [options]

Commands:
  run <model> [ctx] [port]    Start model server
  stop [port]                 Stop server on port (default: 8083)
  status [port]               Check if server is running
  list                        List available models
  path <model>                Show model file path
  chat <model>                Quick chat via curl (one-shot)

Models:
  qwen, qwen35, qwen3.5       Qwen 3.5 9B Uncensored
  gemma, gemma4               Gemma 4 Uncensored  
  gemma-base, gemma-instruct  Gemma 4 Instruct

Examples:
  ai run qwen                 # Start Qwen on port 8083
  ai run qwen 4096 8084       # Start with 4k context on port 8084
  ai stop                     # Kill server on 8083
  ai chat qwen                # Quick chat prompt

HELP
}

# List models
list_models() {
    echo "Available models:"
    for key in ${(k)MODELS}; do
        printf "  %-12s %s\n" "$key" "${MODEL_NAMES[$key]}"
    done
}

# Get model path
get_path() {
    local model=$1
    if [[ -z "$model" ]]; then
        echo "Error: specify model name" >&2
        return 1
    fi
    if [[ -z "${MODELS[$model]}" ]]; then
        echo "Error: unknown model '$model'" >&2
        echo "Run 'ai list' to see available models" >&2
        return 1
    fi
    echo "${MODELS[$model]}"
}

# Run server
run_server() {
    local model=$1
    local ctx=${2:-$DEFAULT_CTX}
    local port=${3:-$DEFAULT_PORT}
    
    local model_path=$(get_path "$model") || return 1
    
    if [[ ! -f "$model_path" ]]; then
        echo "Error: model file not found: $model_path" >&2
        return 1
    fi
    
    echo "Starting ${MODEL_NAMES[$model]}..."
    echo "  Context: $ctx"
    echo "  Port: $port"
    echo "  File: $model_path"
    echo ""
    echo "Server logs:"
    echo "---"
    
    llama-server \
        -m "$model_path" \
        -c "$ctx" \
        --port "$port" \
        --temp "$DEFAULT_TEMP" \
        --top-p "$DEFAULT_TOP_P" \
        --top-k "$DEFAULT_TOP_K" \
        --min-p 0 \
        --reasoning-format none
}

# Stop server
stop_server() {
    local port=${1:-$DEFAULT_PORT}
    local pid=$(lsof -ti tcp:$port 2>/dev/null || echo "")
    
    if [[ -n "$pid" ]]; then
        echo "Stopping server on port $port (PID: $pid)..."
        kill "$pid" 2>/dev/null && echo "Stopped" || echo "Failed to stop"
    else
        echo "No server running on port $port"
    fi
}

# Check status
server_status() {
    local port=${1:-$DEFAULT_PORT}
    local pid=$(lsof -ti tcp:$port 2>/dev/null || echo "")
    
    if [[ -n "$pid" ]]; then
        echo "Server running on port $port (PID: $pid)"
        curl -s http://localhost:$port/health | head -1 || echo "Health check failed"
    else
        echo "No server on port $port"
    fi
}

# Quick chat
quick_chat() {
    local model=$1
    local port=${2:-$DEFAULT_PORT}
    
    if [[ -z "$model" ]]; then
        echo "Usage: ai chat <model> [port]" >&2
        return 1
    fi
    
    # Check if server running
    if ! lsof -ti tcp:$port >/dev/null 2>&1; then
        echo "No server on port $port. Start with: ai run $model" >&2
        return 1
    fi
    
    echo "Enter your message (Ctrl+D to send):"
    local message=$(cat)
    
    curl -s http://localhost:$port/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"local\",
            \"messages\": [{\"role\": \"user\", \"content\": $(echo "$message" | jq -Rs .)}],
            \"temperature\": $DEFAULT_TEMP
        }" | jq -r '.choices[0].message.content' 2>/dev/null || echo "Error: check server status"
}

# Main dispatch
case "$1" in
    run)
        shift
        run_server "$@"
        ;;
    stop)
        shift
        stop_server "$@"
        ;;
    status)
        shift
        server_status "$@"
        ;;
    list|ls)
        list_models
        ;;
    path)
        shift
        get_path "$1"
        ;;
    chat)
        shift
        quick_chat "$@"
        ;;
    help|--help|-h|"")
        show_help
        ;;
    *)
        echo "Unknown command: $1" >&2
        show_help
        exit 1
        ;;
esac
EOF

chmod +x ~/bin/ai
```

## Add to Your PATH

Add this to `~/.zshrc` (if not already there):

```bash
export PATH="$HOME/bin:$PATH"
```

Then reload:
```bash
source ~/.zshrc
```

## Usage

```bash
ai run qwen              # Start Qwen
ai run qwen 4096         # Start with 4k context
ai run qwen 4096 8084    # Start on different port

ai list                  # Show all models
ai path qwen             # Show file location
ai status                # Check if running
ai stop                  # Kill server
ai chat qwen             # Quick one-shot chat (if jq installed)
```

## Bonus: Bash-compatible Version

If you want it to work in bash too, replace the zsh-specific parts:

```bash
# Change this:
typeset -A MODELS
# To this:
declare -A MODELS

# Change this:
for key in ${(k)MODELS}
# To this:
for key in "${!MODELS[@]}"
```

