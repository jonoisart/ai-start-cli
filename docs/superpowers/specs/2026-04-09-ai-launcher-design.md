# AI Launcher — MVP + Registry Design

**Date:** 2026-04-09
**Scope:** MVP launcher with JSON registry and GGUF scanner (Phase 1B)
**Status:** Approved

---

## Goal

A `pip3 install -e .` Python CLI called `ai` that replaces hardcoded model paths with a managed JSON registry, adds GGUF auto-discovery via binary header parsing, and wraps `llama-server` with sane per-model defaults.

---

## Project Structure

```
ai-launcher/
├── pyproject.toml              # package metadata, click entry point
├── Makefile                    # install / uninstall shortcuts
├── src/
│   └── ai/
│       ├── __init__.py
│       ├── cli.py              # click commands — thin dispatch only
│       ├── registry.py         # JSON registry CRUD
│       ├── scanner.py          # GGUF file discovery + binary header parsing
│       └── server.py           # llama-server process management
└── completions/
    └── ai.zsh                  # zsh tab completion
```

---

## Registry Format

Location: `~/.config/ai/registry.json`

```json
{
  "defaults": {
    "port": 8083,
    "temp": 0.7,
    "top_p": 0.8,
    "top_k": 20,
    "min_p": 0,
    "n_gpu_layers": 99,
    "flash_attn": true
  },
  "models": {
    "qwen": {
      "path": "/Users/onoi/.cache/huggingface/hub/models--HauhauCS--Qwen3.5-9B-Uncensored-HauhauCS-Aggressive/snapshots/335e9ef38ada3edf9f9a3a6c2836022c1ab76ea1/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q8_0.gguf",
      "name": "Qwen 3.5 9B Uncensored (Q8_0)",
      "arch": "qwen2",
      "quant": "Q8_0",
      "params": "9B",
      "ctx": 131072,
      "reasoning": false,
      "jinja": true,
      "added": "2026-04-09"
    },
    "gemma": {
      "path": "/Users/onoi/.cache/huggingface/hub/models--HauhauCS--Gemma-4-E4B-Uncensored-HauhauCS-Aggressive/snapshots/45b6a334b4bcd1d7f37179df58b3b1d66a184e5d/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf",
      "name": "Gemma 4 Uncensored (Q4_K_M)",
      "arch": "gemma3",
      "quant": "Q4_K_M",
      "params": "4B",
      "ctx": 131072,
      "reasoning": false,
      "jinja": false,
      "added": "2026-04-09"
    },
    "gemma-base": {
      "path": "/Users/onoi/.cache/huggingface/hub/models--unsloth--gemma-4-E4B-it-GGUF/snapshots/315e03409eb1cdde302488d66e586dea1e82aad1/gemma-4-E4B-it-Q8_0.gguf",
      "name": "Gemma 4 Instruct (Q8_0)",
      "arch": "gemma3",
      "quant": "Q8_0",
      "params": "4B",
      "ctx": 131072,
      "reasoning": false,
      "jinja": false,
      "added": "2026-04-09"
    }
  }
}
```

### Schema Rules

- `defaults` apply to every `ai run` invocation; per-model fields override them.
- `ctx` is required per-model and has no global default — models have hard context limits that differ. `ai scan` and `ai add` always prompt for ctx if it can't be read from the GGUF header.
- `reasoning` (bool): passes `--reasoning-format none` to llama-server when `false`. Only meaningful for thinking models (Qwen3, DeepSeek-R1, etc.).
- `jinja` (bool): passes `--jinja` flag when `true`. Required for models with complex Jinja chat templates.
- `n_gpu_layers: 99` means "offload as many layers as possible" — llama-server caps at actual layer count.
- `flash_attn: true` enables Flash Attention for faster, lower-memory inference on Apple Silicon.

---

## Commands

### `ai run <model> [--ctx N] [--port N] [--temp F]`

Starts `llama-server` in the foreground. CLI flags override registry values.

Built argv merges in this order (lowest → highest priority):
1. Global defaults
2. Per-model registry values
3. CLI flags passed at invocation

Flags translated to llama-server:
- `ctx` → `-c`
- `port` → `--port`
- `temp` → `--temp`
- `top_p` → `--top-p`
- `top_k` → `--top-k`
- `min_p` → `--min-p`
- `n_gpu_layers` → `-ngl`
- `flash_attn: true` → `-fa on`
- `reasoning: false` → `--reasoning-format none`
- `jinja: true` → `--jinja`

### `ai stop [--port N]`

Finds PID via `lsof -ti tcp:<port>` and sends SIGTERM. Defaults to port 8083.

### `ai status [--port N]`

Hits `http://localhost:<port>/health`. Prints running/stopped + PID if running.

### `ai list`

Prints all registry models in a table: nickname, name, quant, params, ctx, path.

### `ai path <model>`

Prints the absolute path for the given nickname. Useful for piping to other tools.

### `ai chat <model> [message] [--port N]`

If `message` is provided: one-shot POST to `/v1/chat/completions`, print response.
If no `message`: read from stdin (pipe-friendly).
Requires server already running on the given port.

### `ai scan [path] [--depth N] [--auto]`  (default depth: 5)

Walks `path` (or default locations if omitted) for `*.gguf` files. For each file not already in registry:
1. Parse GGUF binary header to extract arch, quant, ctx, params.
2. In interactive mode: show metadata, prompt for nickname, confirm add.
3. With `--auto`: add all found models using filename-derived nicknames, no prompts.

Default scan locations (in order):
- `~/.cache/huggingface/hub/`
- `~/.cache/llama.cpp/`
- `~/Downloads/`
- `/Volumes/` (mounted external drives)

### `ai add <path> <nickname>`

Manually register a GGUF file. Parses GGUF header to auto-detect `arch`, `quant`, `ctx`, `params`. Always prompts for:
- `reasoning` (bool, default: false)
- `jinja` (bool, default: false)
- `name` (display name, default: derived from filename)

### `ai remove <nickname>`

Removes model entry from registry. Does not delete the file.

---

## Module Responsibilities

### `registry.py`

- `load() -> dict` — read and parse `~/.config/ai/registry.json`, create with defaults if missing
- `save(data: dict)` — write registry atomically (write to `.tmp`, then rename)
- `get_model(name: str) -> dict` — return model record, raise `ClickException` if not found
- `add_model(nickname: str, record: dict)` — add or overwrite entry, save
- `remove_model(nickname: str)` — remove entry, save
- `merge_defaults(model: dict, defaults: dict) -> dict` — model values override defaults

### `scanner.py`

- `find_ggufs(path: str, depth: int) -> list[Path]` — recursive glob for `*.gguf`
- `parse_gguf_header(path: Path) -> dict` — read binary header, return `{arch, quant, ctx, params}`
- `is_registered(path: Path, registry: dict) -> bool` — check if path already in registry
- `nickname_from_filename(path: Path) -> str` — derive a reasonable default nickname

GGUF header parsing reads the first ~4KB of the file:
- Magic: bytes 0-3 = `GGUF`
- Version: uint32 at offset 4
- Metadata key-value pairs follow a defined binary format
- Target keys: `general.architecture`, `general.quantization_version`, `llama.context_length` (or `{arch}.context_length`), `general.parameter_count`
- On parse failure: return empty dict, flag result as `unverified: true`

### `server.py`

- `build_argv(model: dict) -> list[str]` — construct full `llama-server` arg list
- `run(argv: list[str])` — `os.execvp` into llama-server (replaces process)
- `stop(port: int)` — find and kill PID
- `status(port: int) -> dict` — check port + hit `/health`
- `find_llama_server() -> str` — locate binary via PATH, raise with install hint if missing

### `cli.py`

Click group with one `@cli.command()` per command above. Each command:
1. Loads registry
2. Calls into the appropriate module
3. Handles `ClickException` for user-facing errors

No business logic in `cli.py`.

---

## Error Handling

| Scenario | Response |
|----------|----------|
| Nickname not in registry | "Unknown model 'foo'. Run `ai list` to see available models." |
| Model file missing from disk | "Model file not found: <path>. Re-run `ai scan` or `ai add`." |
| Port already in use | "Port <N> in use (PID <pid>). Run `ai stop --port <N>` first." |
| `llama-server` not in PATH | "llama-server not found. Install with: brew install llama.cpp" |
| `ai chat` with no server running | "No server on port <N>. Start with: ai run <model>" |
| GGUF header parse failure | Proceed with filename heuristics, mark entry `"unverified": true` |
| Registry file corrupt | Print path, suggest deleting and re-running `ai scan` |

---

## Dependencies

| Package | Why |
|---------|-----|
| `click` | CLI framework |

`jq` is NOT required — all JSON handled natively in Python. `lsof` is macOS stdlib.

---

## Out of Scope (Phase 2+)

- Background daemon mode (`ai start` / `ai ps` / `ai logs`)
- HuggingFace download (`ai install`)
- Onboarding wizard (`ai init`)
- TUI mode
- Migration from Ollama/LM Studio
- Shell completions (stubbed file only, not wired)
- Windows/Linux support
