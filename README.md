# ai-launcher

A command-line launcher for local GGUF models. Wraps `llama-server` from llama.cpp so you type `ai start qwen` instead of a 200-character HuggingFace cache path plus a dozen tuning flags.

```bash
ai scan                # find GGUF files on disk, register them with nicknames
ai start qwen          # launch llama-server with that model's saved settings
ai chat qwen "hello"   # one-shot prompt against the running server
```

Offline after setup. No telemetry, no API keys, no update checks. macOS only.

For how the project got here, see [HISTORY.md](HISTORY.md).

---

## Requirements

- macOS (uses `lsof`; default scan paths assume macOS conventions)
- Python 3.11+
- `llama-server` on your `PATH` — `brew install llama.cpp`

Runtime dependency is `click`. Everything else is standard library.

## Install

```bash
git clone git@github.com:jonoisart/ai-start-cli.git
cd ai-start-cli
make dev
```

`make dev` creates `.venv`, installs the package in editable mode, and symlinks `~/.local/bin/ai` into it. Editing `src/` takes effect immediately with no reinstall. Make sure `~/.local/bin` is on your `PATH`.

| Target | Does |
|---|---|
| `make dev` | Editable install plus symlink — what you want for development |
| `make install` | Regular install plus symlink |
| `make uninstall` | Removes the package and the symlink |
| `make test` | Runs the test suite |

---

## Commands

Everything listed here is built and working.

| Command | Does |
|---|---|
| `ai scan [path]` | Walk for `.gguf` files, prompt to register each new one |
| `ai add <path> <nickname>` | Register a single file by hand |
| `ai remove <nickname>` | Drop from the registry (does not delete the file) |
| `ai list` | Table of registered models |
| `ai path <model>` | Print the file path, pipe-friendly |
| `ai start <model>` | Launch llama-server in the foreground |
| `ai stop` | SIGTERM whatever is listening on the port |
| `ai status` | Check the port, then hit `/health` |
| `ai chat <model> [message]` | One-shot POST to `/v1/chat/completions` |

### Options

```bash
ai scan ~/Downloads --depth 3    # how deep to walk (default 5)
ai scan --auto                   # register everything found, no prompts

ai start qwen --ctx 8192         # override context window
ai start qwen --port 8084        # override port
ai start qwen --temp 0.2         # override temperature

ai stop --port 8084              # target a specific port
ai status --port 8084

ai chat qwen --port 8084
cat prompt.txt | ai chat qwen    # reads stdin when no message is given
```

### Discovering models

`ai scan` with no path searches `~/.cache/huggingface/hub`, `~/.cache/llama.cpp`, `~/Downloads`, and `/Volumes`. For each `.gguf` it finds that isn't already registered, it reads the file's binary header to pull out architecture, quantization, parameter count, and context length, then asks you for a nickname.

Files whose headers can't be parsed still get registered using filename heuristics, tagged `"unverified": true`.

---

## Configuration

Two JSON files in `~/.config/ai/`.

**`config.json`** — your settings, applied to every model.

```json
{ "port": 8083, "temp": 0.7, "top_p": 0.8, "top_k": 20,
  "min_p": 0, "n_gpu_layers": 99, "flash_attn": true }
```

**`registry.json`** — the model database, rebuilt freely by `ai scan`.

```json
{
  "models": {
    "qwen": {
      "path": "/Users/you/.cache/huggingface/hub/.../Qwen3.5-9B-Q8_0.gguf",
      "name": "Qwen 3.5 9B Uncensored",
      "arch": "qwen35", "quant": "Q8_0", "params": "9B",
      "ctx": 131072, "reasoning": false, "jinja": true,
      "added": "2026-04-28"
    }
  }
}
```

They're separate files so that wiping and rebuilding the model list can't take your settings with it.

### Settings precedence

Lowest to highest:

| Layer | Source | Example |
|---|---|---|
| Global | `config.json` | `temp: 0.7` applies everywhere |
| Per-model | the model's registry record | `qwen` sets `jinja: true` |
| CLI flag | what you typed | `--port 8084` beats both |

### Per-model fields

| Field | Meaning |
|---|---|
| `ctx` | Context window. Required — models have different hard limits, so there's no global default. |
| `reasoning` | `false` passes `--reasoning-format none`, suppressing thinking output. Only meaningful for reasoning models. |
| `jinja` | `true` passes `--jinja`. Needed by models with complex chat templates. |
| `n_gpu_layers` | `99` means "offload everything"; llama-server caps it at the real layer count. |
| `flash_attn` | `true` passes `-fa on`. Faster and lower-memory on Apple Silicon. |
| `cache_type_k`, `cache_type_v` | KV cache precision, passed as `-ctk`/`-ctv`. Omitted by default, which means llama-server's `f16`. |

### Fitting a model in memory

The KV cache, not the model file, is usually what breaks a large context. It scales linearly with `ctx`, and at `f16` it is expensive: a 9B model at 131072 context needs roughly 16 GB of cache on top of the ~9 GB of weights.

Setting `cache_type_k` and `cache_type_v` to `q8_0` halves that at close to no quality cost, and is often the difference between a context fitting and not:

```json
"cache_type_k": "q8_0",
"cache_type_v": "q8_0"
```

Quantized cache types require flash attention. `ai start` refuses upfront rather than letting llama-server fail after the process has been replaced.

Rough sizing, per token: `2 × layers × n_head_kv × (embed / n_head) × bytes_per_element`. Every term comes from the GGUF header. Models using grouped-query attention (`n_head_kv` well below `n_head`) are far cheaper than the parameter count suggests.

Both paths can be overridden with `AI_CONFIG_PATH` and `AI_REGISTRY_PATH`, which is how the test suite stays off your real files.

---

## How it works

```
cli.py  ──┬──►  config.py      user settings, plus one-time migration
          ├──►  registry.py    JSON CRUD on the model database
          ├──►  scanner.py     find .gguf files, parse their binary headers
          └──►  server.py      build argv, start/stop/status the process

config.py ────►  registry.py   the one inter-module import
```

`cli.py` holds no business logic. Every command loads state, calls a module, and prints. The one dependency between worker modules runs `config → registry`, so migration can lift a legacy `defaults` block out of the registry; it never runs the other way.

**Starting a server** resolves settings through the three layers above, checks the port is free via `lsof -ti tcp:<port> -sTCP:LISTEN`, builds the argv, then calls `os.execvp`. That *replaces* the Python process rather than spawning a child, so llama-server inherits the PID. This is why `ai start` blocks your terminal, why Ctrl-C reaches the server directly, and why there's no background mode yet.

**GGUF parsing** reads model metadata straight out of the binary with `struct`, no dependency involved. The parser walks key-value pairs looking for `general.architecture`, `general.file_type`, `general.parameter_count`, and `*.context_length`, skipping array values (tokenizer vocabularies live there and run to hundreds of thousands of entries). Any parse failure degrades to filename heuristics rather than crashing the scan.

**Writes are atomic.** Both JSON files serialize to a `.tmp` sibling then `rename()` over the target, which is atomic on POSIX, so an interrupted write can't leave a half-written file.

---

## Development

```bash
make test                                # full suite
.venv/bin/python -m pytest tests/ -v     # same thing, directly
```

```
src/ai/                    cli.py, config.py, registry.py, scanner.py, server.py
tests/                     conftest.py + one module per source module
completions/               ai.zsh (stub, not wired up)
docs/superpowers/specs/    design docs
```

Two test conventions worth knowing:

**Path redirection.** `tests/conftest.py` has an autouse fixture pinning `AI_CONFIG_PATH` and `AI_REGISTRY_PATH` into a pytest `tmp_path` for every test. It isn't optional — migration *writes* to `registry.json`, so an unisolated test could rewrite your real config.

**`banana` means "arbitrary".** Placeholder values in tests are named `banana` so a reader can tell instantly which values the code actually cares about. The exception is `tests/test_scanner.py`, which uses realistic filenames like `Qwen3.5-9B-Uncensored-Q8_0.gguf` because parsing those patterns is the thing under test.

---

## Not built yet

Nothing in this section exists. It's here so the command table above stays honest.

**Next up:**

- `ai init` — first-run setup wizard. `config.json` now exists, so it has somewhere to write.
- `ai install` — pull quantizations from HuggingFace.
- mlx-lm support — detect mlx-lm models in `ai scan`, launch them from `ai start`.

**Later:**

- Background mode — `ai ps`, `ai logs`, log rotation. Needs a real daemon, not a flag; see the `execvp` note above.
- Shell completions, wired up properly.
- Migration from Ollama, LM Studio, koboldcpp.
- TUI model browser.

## Current limitations

- **No background mode.** `ai start` runs in the foreground.
- **macOS only.** `lsof` invocation and default scan paths assume it.
- **GGUF only.** No mlx-lm, no Ollama or LM Studio import.
- **Shell completion is a stub.** `completions/ai.zsh` exists but isn't wired up.

## License

MIT.
