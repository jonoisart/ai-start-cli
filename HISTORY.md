# History

How this tool got here. For what it does today, see [README.md](README.md).

---

## v0 — the zsh script (2026-04-09)

It started as a ~200-line zsh script at `~/bin/ai`, with model paths hardcoded in an associative array:

```zsh
typeset -A MODELS
MODELS=(
    qwen   "/Users/onoi/.cache/huggingface/hub/models--HauhauCS--Qwen3.5-9B-.../Qwen3.5-9B-...-Q8_0.gguf"
    qwen35 "/Users/onoi/.cache/huggingface/hub/models--HauhauCS--Qwen3.5-9B-.../Qwen3.5-9B-...-Q8_0.gguf"
    gemma  "/Users/onoi/.cache/huggingface/hub/models--HauhauCS--Gemma-4-E4B-.../Gemma-4-...-Q4_K_M.gguf"
)
```

Commands were `ai run`, `stop`, `status`, `list`, `path`, `chat`. It worked, and it solved the actual problem, which was never typing those paths again.

What it couldn't do:

- Adding a model meant editing the script. Nicknames and aliases were hand-maintained duplicate entries.
- Every model shared one set of flags. `DEFAULT_CTX=131072` was applied to everything regardless of what the model actually supported.
- `ai chat` shelled out to `curl` and `jq`, so chat silently broke without `jq` installed.
- No way to find models you'd downloaded but not yet registered.

## Phase 1 — Python rewrite (2026-04-10 → 04-28)

Rebuilt as a pip-installable Click CLI with a JSON registry. Same idea, but models become data instead of source code.

Built in dependency order, test-first:

| Date | Commit | What |
|---|---|---|
| 04-10 | `04988e5` | Package scaffold, Click entry point |
| 04-10 | `e6b46b9` | `registry.py` — JSON CRUD, atomic save |
| 04-12 | `68eee77` | `scanner.py` — GGUF binary header parser |
| 04-13 | `72b42c4` | Depth-limited filesystem walk for `.gguf` |
| 04-13 | `6c55d1e` | `server.py` — llama-server process management |
| 04-27 | `7d3b151` | All CLI commands wired |
| 04-28 | `e3b7d7b` | `scan`, `add`, `start`, `stop`, `remove` working end to end |

What changed for the user:

- Models live in `~/.config/ai/registry.json`. `ai add` and `ai scan` register them; no source edits.
- Per-model settings. `ctx`, `reasoning`, and `jinja` are stored per model, since a 4B and a 9B don't want the same flags.
- `ai scan` reads GGUF binary headers directly with `struct` to auto-detect architecture, quantization, parameter count, and context length.
- `jq` and `curl` dropped in favor of `urllib.request`. Chat has no external dependencies now.
- `ai run` became `ai start`.

### Things that went wrong along the way

**`lsof` returned multiple PIDs** (`ca9f00f`). `lsof -ti tcp:8083` lists every process touching that port, including *clients connected to it*, so `int(output)` blew up once anything was talking to the server. Fixed by adding `-sTCP:LISTEN` to select only the listening socket.

**Quantization suffixes didn't all match** (`3d454bd`). The nickname deriver cut filenames at the quant marker with `[-_][Qq][0-9]`, which silently missed `IQ4_XS` and friends. Extended to catch the `IQ` prefix.

**Registry records without a `path` key** crashed `is_registered` (`0ffbdb4`). Guarded.

**`save()` assumed its directory existed** (`1ce1a85`). It didn't on a fresh install.

**The symlink went to `~/bin`** (`bd1420a`), which isn't on `PATH` by default on modern macOS. Moved to `~/.local/bin`.

**Detected context length couldn't be overridden.** `ai add` used `meta.get("ctx") or prompt(...)`, so if the GGUF header declared a context window, you were stuck with it — no way to cap a 131072-context model at something your RAM could actually hold. Changed to always prompt, using the detected value as the default.

## Phase 2 — config extraction (2026-08-09)

`registry.json` held two unrelated things: a `defaults` block of user settings and a `models` map of discovered files. Since `ai scan` rebuilds the registry, wiping the model list took your settings with it. The planned setup wizard also needed somewhere to write that wasn't the model database.

Split into two files:

```
~/.config/ai/config.json     user settings
~/.config/ai/registry.json   discovered models
```

Existing installs migrate automatically the first time `config.load()` finds no `config.json`. The config file is written *before* the registry is stripped, deliberately: a crash between the two leaves a stale `defaults` key that the next run ignores, whereas the reverse order would lose your settings outright.

Also landed in this phase:

- `--alias` and `--embeddings`/`--pooling` passed through to llama-server.
- `tests/conftest.py` with an autouse fixture pinning both config paths into a temp directory. Not optional: migration *writes* to `registry.json`, so an unisolated test could rewrite a real config.
- Test placeholders renamed to `banana`, so it's obvious at a glance which values the code actually cares about.
- Fixed `test_save_is_atomic`, which asserted against `registry.json.tmp` when `with_suffix(".tmp")` produces `registry.tmp`. The assertion could never fail.

---

## The original roadmap, for reference

The first README sketched five phases. Recording where the thinking started, since it's diverged:

| Phase | Planned | Status |
|---|---|---|
| 1 | Config system, JSON registry, background daemon, model discovery | Registry and discovery shipped. Config split shipped in Phase 2. Daemon not built. |
| 2 | `ai install` from HuggingFace, search, update management | Not built |
| 3 | Onboarding wizard, multiple install methods, migration from Ollama/LM Studio | Not built |
| 4 | TUI mode, chat REPL, model router | `ai chat` shipped as one-shot only. Rest not built. |
| 5 | Plugin system, remote models, model versioning | Not built |

Two assumptions from that roadmap turned out wrong:

**Background mode was assumed easy.** `ai start` uses `os.execvp`, which replaces the Python process rather than spawning a child. That's what makes Ctrl-C reach the server directly, but it also means backgrounding needs a real `fork()` or daemon, not a flag.

**The README claimed `ai ps`, `ai logs`, and background mode as shipped** for months while none of them existed. Documenting intentions in the same table as reality is how that happened; the current README keeps built and planned features in separate sections.
