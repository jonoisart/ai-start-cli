# Config Extraction — Split Defaults Out of the Registry

**Date:** 2026-08-09
**Scope:** Move the `defaults` block from `registry.json` into its own `config.json` (Phase 1)
**Status:** Approved

---

## Goal

Separate user settings from model data. Today `~/.config/ai/registry.json` holds both a `defaults` block and a `models` map. Splitting them gives `ai init` a config file to write without touching model records, and lets the registry be deleted and rebuilt by `ai scan` without losing user preferences.

This is deliberately narrow. No new settings, no new commands, no behavior change visible to the user beyond a one-time migration notice.

---

## File Layout

**Before**

```
~/.config/ai/registry.json     { "defaults": {...}, "models": {...} }
```

**After**

```
~/.config/ai/config.json       { "port": 8083, "temp": 0.7, ... }
~/.config/ai/registry.json     { "models": {...} }
```

`config.json` is flat. The seven fields sit at the top level, not nested under a `defaults` key, because the file's entire purpose is to hold defaults.

---

## New Module: `src/ai/config.py`

Mirrors `registry.py`'s structure and idioms.

```python
DEFAULT_CONFIG = {
    "port": 8083,
    "temp": 0.7,
    "top_p": 0.8,
    "top_k": 20,
    "min_p": 0,
    "n_gpu_layers": 99,
    "flash_attn": True,
}
```

Public, unlike `registry._DEFAULT`, because migration backfill and tests both reference it.

| Function | Behavior |
|---|---|
| `_path() -> Path` | `~/.config/ai/config.json`, overridable via `AI_CONFIG_PATH`. Same pattern as `registry._path()` and `AI_REGISTRY_PATH`. |
| `load() -> dict` | Returns config. Reads the file if present; otherwise attempts migration; otherwise returns `dict(DEFAULT_CONFIG)`. |
| `save(data: dict) -> None` | Atomic write to `config.tmp` then rename, with `parents=True` mkdir guard. Identical to `registry.save`. |
| `_migrate_from_registry() -> dict \| None` | One-time move of the legacy `defaults` block. Returns `None` when there is nothing to migrate. |

`DEFAULT_CONFIG` is flat, so `dict(...)` is a sufficient copy. No `deepcopy` needed.

### Registry changes

`registry._DEFAULT` shrinks to `{"models": {}}`. The `defaults` key leaves the registry schema entirely.

`merge_defaults(model, defaults)` is unchanged. It is a pure dict merge and does not care which file the defaults came from.

---

## Dependency Direction

```
cli.py → config.py → registry.py
```

One direction only. `registry.py` never imports `config.py` and stays unaware it exists. `config.py` uses only `registry.load()` and `registry.save()`, both already public, so nothing new needs exposing.

---

## Migration

Runs inside `config.load()` when `config.json` is absent.

```python
def load() -> dict:
    p = _path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            raise click.ClickException(
                f"Config file is corrupt: {p}\nDelete it to regenerate defaults."
            )
    migrated = _migrate_from_registry()
    if migrated is not None:
        return migrated
    p.parent.mkdir(parents=True, exist_ok=True)
    return dict(DEFAULT_CONFIG)
```

`_migrate_from_registry()`:

1. `reg = registry.load()`
2. If `"defaults"` not in `reg`, return `None`. Nothing to migrate.
3. `legacy = reg.pop("defaults")`
4. `cfg = {**DEFAULT_CONFIG, **legacy}` so any field the old registry lacked still gets a value
5. `save(cfg)` — **write config.json first**
6. `registry.save(reg)` — **then** persist the stripped registry
7. Notify on stderr, return `cfg`

### Why the write order matters

A crash between steps 5 and 6 leaves a stale `defaults` key in `registry.json`. On the next run `config.json` exists, migration is skipped, and that key is simply ignored dead data. Harmless.

The reverse order would strip the registry first and lose the user's custom values if the config write then failed. So config is always written before the registry is stripped.

### Detecting "nothing to migrate"

No filesystem existence check is required. Once `registry._DEFAULT` is `{"models": {}}`, a missing `registry.json` makes `registry.load()` return a dict with no `defaults` key, so step 2 correctly no-ops.

### Corrupt registry during migration

`registry.load()` raises `ClickException` on malformed JSON and that exception propagates. A user running `ai status` with a corrupt registry sees "Registry file is corrupt" rather than a config error. The message is accurate and actionable, so it is not caught or masked.

### Migration notice

```python
click.echo(f"Migrated defaults from registry.json to {_path()}", err=True)
```

Stderr, not stdout, so `ai path qwen | pbcopy` stays clean.

---

## Call Sites

Four lines in `cli.py`. Each affected command calls `config.load()` alongside `registry.load()`.

| Line | Command | Before | After |
|---|---|---|---|
| 56 | `status` | `reg["defaults"].get("port", 8083)` | `cfg.get("port", 8083)` |
| 73 | `stop` | `reg["defaults"].get("port", 8083)` | `cfg.get("port", 8083)` |
| 94 | `start` | `registry.merge_defaults(m, reg["defaults"])` | `registry.merge_defaults(m, cfg)` |
| 124 | `chat` | `registry.merge_defaults(m, reg["defaults"])` | `registry.merge_defaults(m, cfg)` |

Import line becomes `from ai import config, registry, scanner, server`.

`list`, `path`, `scan`, `add`, and `remove` do not read defaults and are untouched.

---

## Testing

### New: `tests/conftest.py`

```python
@pytest.fixture(autouse=True)
def isolate_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_REGISTRY_PATH", str(tmp_path / "registry.json"))
    monkeypatch.setenv("AI_CONFIG_PATH", str(tmp_path / "config.json"))
```

Autouse and mandatory. Migration *writes* to `registry.json`, so any test that reaches `config.load()` without isolation would rewrite the developer's real `~/.config/ai/registry.json`. `monkeypatch` restores the prior environment automatically.

### New: `tests/test_config.py`

| Test | Asserts |
|---|---|
| `test_load_creates_default_when_missing` | Returns `DEFAULT_CONFIG` values, `port == 8083` |
| `test_load_reads_existing` | Hand-written `config.json` with `port: 9999` is returned verbatim |
| `test_load_corrupt_raises` | Malformed JSON raises `ClickException` |
| `test_save_is_atomic` | File written, no `config.tmp` left behind |
| `test_migrates_defaults_from_registry` | Legacy `defaults` land in the returned config |
| `test_migration_strips_defaults_from_registry` | `registry.json` on disk no longer has a `defaults` key |
| `test_migration_backfills_missing_fields` | Legacy block with only `port` still yields all seven fields |
| `test_existing_config_wins_over_registry_defaults` | With both files present, `config.json` is used and the registry is left untouched |
| `test_no_migration_when_registry_missing` | Absent `registry.json` yields `DEFAULT_CONFIG`, no crash |

### Edits: `tests/test_registry.py`

- `reg_path` fixture reduces to `return tmp_path / "registry.json"`. The autouse conftest fixture now owns the env var.
- `test_load_creates_default_when_missing` asserts `data == {"models": {}}` instead of checking `defaults` and `port`.
- `test_load_reads_existing` rewritten around a `models` entry rather than `defaults`.
- `test_get_model_found` fixture dict drops its `"defaults": {}` key.
- `test_merge_defaults` unchanged. Still valid as a pure-function test.

The suite keeps all 46 existing tests, four of them reworked as above, and adds the nine new config tests. Everything must be green before the work is considered done.

---

## Error Handling

| Scenario | Response |
|---|---|
| `config.json` corrupt | "Config file is corrupt: `<path>`. Delete it to regenerate defaults." |
| `registry.json` corrupt during migration | Existing registry-corrupt error propagates unchanged |
| `config.json` missing, registry has `defaults` | Silent migration plus a one-line stderr notice |
| `config.json` missing, registry has no `defaults` | `DEFAULT_CONFIG` returned, nothing written |
| Crash mid-migration | Stale `defaults` in registry ignored on next run |

---

## Out of Scope

- `ai config get` / `ai config set` commands
- User-configurable scan paths (`scanner.DEFAULT_SCAN_PATHS` stays hardcoded)
- Profile presets such as "coding" or "creative"
- YAML format and the `pyyaml` dependency
- Any change to `merge_defaults` precedence
