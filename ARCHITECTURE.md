# Architecture

How `ai-launcher` is put together, written for someone (probably future you) coming back to it cold.

---

## What it does

`ai` wraps `llama-server` from llama.cpp. Without it, launching a model means typing a 200-character HuggingFace cache path plus a dozen tuning flags. With it:

```bash
ai start qwen
```

Everything else in the codebase is bookkeeping in service of that one line.

---

## Install layout

`pyproject.toml` declares a console-script entry point:

```toml
[project.scripts]
ai = "ai.cli:cli"
```

`make dev` creates `.venv`, runs `pip install -e ".[dev]"`, then symlinks `~/.local/bin/ai` → `.venv/bin/ai`. So the command on your PATH points into the repo's venv, and editing `src/` takes effect immediately with no reinstall.

Runtime dependency is `click` alone. Everything else is stdlib: `struct`, `json`, `pathlib`, `urllib.request`, `subprocess`, `shutil`. `pytest` is dev-only.

---

## Module map

```
cli.py  ──┬──►  config.py      user settings, plus one-time migration
          ├──►  registry.py    JSON CRUD on the model database
          ├──►  scanner.py     find .gguf files, parse their binary headers
          └──►  server.py      build argv, start/stop/status the process

config.py ────►  registry.py   migration only — the one inter-module import
```

`cli.py` is the only coordinator and holds no business logic — every command loads state, calls into a module, and prints. The one dependency between worker modules runs `config → registry`, so that migration can read a legacy `defaults` block and write the stripped registry back. It never runs the other way: `registry.py` does not know `config.py` exists.

| Module | Responsibility |
|---|---|
| `cli.py` | Click command definitions and wiring |
| `config.py` | Read/write `config.json`, migrate legacy defaults out of the registry |
| `registry.py` | Read/write `registry.json`, look up and mutate model records |
| `scanner.py` | Walk the filesystem for `.gguf`, decode GGUF headers, derive nicknames |
| `server.py` | Locate the binary, construct the command line, manage the process |

---

## Data files

Two files, both in `~/.config/ai/`. They were one file until config extraction split them, so that `ai scan` rebuilding the model list cannot destroy your settings.

**`config.json`** — user settings. Flat, seven keys.

```json
{ "port": 8083, "temp": 0.7, "top_p": 0.8, "top_k": 20,
  "min_p": 0, "n_gpu_layers": 99, "flash_attn": true }
```

**`registry.json`** — the model database.

```json
{
  "models": {
    "qwen": {
      "path": "/Users/…/Qwen3.5-9B-…-Q8_0.gguf",
      "name": "qwen3.5-9B-Q8-xxx",
      "arch": "qwen35", "quant": "Q8_0", "params": "unknown",
      "ctx": 131072, "reasoning": false, "jinja": true,
      "added": "2026-04-28"
    }
  }
}
```

Both modules resolve their path through an environment variable — `AI_REGISTRY_PATH` and `AI_CONFIG_PATH` respectively:

```python
def _path() -> Path:
    return Path(os.environ.get("AI_REGISTRY_PATH", "~/.config/ai/registry.json")).expanduser()
```

The default is what you use day to day. Tests override both variables to point at a temp directory, which is the entire file-isolation strategy.

Writes are atomic: serialize to a `.tmp` sibling, then `rename()` over the target. `rename` is atomic on POSIX, so an interrupted write can never leave a half-written file.

**Migration.** On the first `config.load()` where `config.json` is absent, `_migrate_from_registry()` moves any legacy `defaults` block out of the registry and announces it on stderr. It writes `config.json` *before* stripping the registry — a crash between the two leaves a stale `defaults` key that the next run ignores, whereas the reverse order would lose your settings. Detection needs no filesystem check: `registry._DEFAULT` is `{"models": {}}`, so a missing registry yields a dict with no `defaults` key.

---

## Trace: `ai start qwen`

The fastest way to load the whole design into your head.

**1. Click routes it.** The `@cli.command()` decorator on `start()` registers the subcommand; `@click.argument("model")` binds `qwen` to the `model` parameter. `ai --help` is generated from these decorators.

**2. Look up the model.**

```python
reg = registry.load()
m = registry.get_model(reg, "qwen")   # raises ClickException if unknown
```

**3. Verify the file still exists.** GGUFs live in caches that get pruned, so a registry entry can outlive its file. Failing here gives a clear message instead of a confusing llama-server error.

**4. Resolve settings through three layers.**

```python
merged = registry.merge_defaults(m, cfg)
if ctx is not None:
    merged["ctx"] = ctx
```

`merge_defaults` is the whole mechanism:

```python
def merge_defaults(model, defaults):
    merged = dict(defaults)   # start from globals
    merged.update(model)      # model record overwrites
    return merged
```

Precedence, lowest to highest:

| Layer | Source | Example |
|---|---|---|
| Global defaults | `config.json` | `temp: 0.7` applies everywhere |
| Per-model | the model's record | `qwen` sets `jinja: true` |
| CLI flags | what you typed | `--port 8084` beats both |

**5. Check the port.**

```python
subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"], ...)
```

`-sTCP:LISTEN` is load-bearing. Without it `lsof` also returns PIDs of clients *connected to* that port, yielding multiple lines that blow up the `int()` conversion.

**6. Build the argv.** `server.build_argv()` maps the settings dict onto llama.cpp flags:

| Setting | Flag |
|---|---|
| `path` | `-m` |
| `ctx` | `-c` |
| `port` / `temp` / `top_p` / `top_k` / `min_p` | `--port` / `--temp` / `--top-p` / `--top-k` / `--min-p` |
| `n_gpu_layers` | `-ngl` |
| `flash_attn: true` | `-fa on` |
| `reasoning: false` | `--reasoning-format none` |
| `jinja: true` | `--jinja` |
| `name` | `--alias` |
| `embeddings` (default on) | `--embeddings --pooling mean` |

One line reads backwards and is worth flagging:

```python
if not model.get("reasoning", True):
    argv += ["--reasoning-format", "none"]
```

A registry value of `reasoning: false` means "suppress the model's thinking output", which is expressed by *adding* the `--reasoning-format none` flag.

**7. Become llama-server.**

```python
def start(argv):
    os.execvp(argv[0], argv)
```

`execvp` replaces the current process image rather than spawning a child. The Python interpreter ceases to exist and llama-server inherits its PID. This is why `ai start` blocks your terminal and why Ctrl-C reaches the server directly. It's also why there is no background mode: that needs `fork()` or a real daemon, which is deliberately out of scope for now.

---

## GGUF header parsing

`scanner.parse_gguf_header()` reads model metadata straight out of the binary, no dependency required. That's how `ai scan` knows a file's quantization and context length without being told.

Layout (v2/v3; v1 uses 32-bit lengths where v2+ uses 64-bit):

```
bytes 0–3    magic "GGUF"
bytes 4–7    version           uint32 LE
bytes 8–15   tensor count      uint64 LE
bytes 16–23  KV count          uint64 LE
then KV pairs: [key_len:u64][key][value_type:u32][value]
```

The parser walks KV pairs looking for four keys, and stops early once it has all four:

| Key | Extracted as |
|---|---|
| `general.architecture` | `arch` |
| `general.file_type` | `quant`, via the `FILE_TYPE_NAMES` int → name table |
| `general.parameter_count` | `params`, formatted as `7B` / `700M` |
| `*.context_length` | `ctx` (prefix varies by architecture, so matched by suffix) |

Array values (type 9) are skipped wholesale by `_skip_array` — tokenizer vocabularies live in these and can be hundreds of thousands of entries.

The whole function is wrapped in `try/except Exception: return {}`. A malformed or truncated GGUF degrades to filename heuristics and the record gets tagged `"unverified": true` rather than crashing the scan.

---

## Commands

| Command | Does |
|---|---|
| `ai list` | Table of registered models |
| `ai path <model>` | Print the file path (pipe-friendly) |
| `ai start <model>` | Launch llama-server in the foreground |
| `ai stop [--port N]` | SIGTERM whatever is listening on the port |
| `ai status [--port N]` | Check the port, then hit `/health` |
| `ai chat <model> [msg]` | One-shot POST to `/v1/chat/completions`; reads stdin if no message |
| `ai scan [path]` | Walk for `.gguf`, prompt to register each new find |
| `ai add <path> <nick>` | Register one file manually |
| `ai remove <nick>` | Drop from the registry; does not delete the file |

---

## Testing

`make test` runs pytest. 46 tests, no network, no real files touched.

Two techniques carry the suite:

**Path redirection.** Set `AI_REGISTRY_PATH` to a `tmp_path` and the module under test reads and writes there instead of your real config.

**Synthetic GGUFs.** `tests/test_scanner.py` has a `gguf_v3()` helper that assembles valid GGUF byte sequences with `struct.pack`, so header parsing is tested against real binary layouts without shipping multi-gigabyte fixtures.

`server.py` tests use `unittest.mock.patch` on `subprocess.run`, `shutil.which`, and `os.kill` so nothing is actually spawned or signalled.

---

## Known gaps

- **README drift.** `README.md` lists `ai ps`, `ai logs`, and background mode as shipped. None exist. Treat that table as aspirational.
- **No background mode.** Blocked on `execvp`, see above.
- **`completions/ai.zsh` is a stub.** Not wired up.
- **macOS only.** `lsof` invocation and default scan paths assume it.
- **`newreadme.md`** is loose roadmap brainstorming, not authoritative.

---

## Planned work

Next up, in rough priority order:

- **`ai init`** — first-run setup wizard. `config.json` exists so this has somewhere to write.
- **`ai install`** — download quantizations from HuggingFace.
- **mlx-lm support** — detect mlx-lm models in `ai scan`, launch them from `ai start`.

Specs and plans live under `docs/superpowers/`. Design docs go in `specs/`, task-by-task implementation plans in `plans/`.
