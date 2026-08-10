# Config Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the `defaults` block out of `~/.config/ai/registry.json` into its own `~/.config/ai/config.json`, with a one-time automatic migration for existing installs.

**Architecture:** A new `src/ai/config.py` mirrors the structure of the existing `src/ai/registry.py` — module-level default dict, `_path()` reading an environment variable override, `load()`, and an atomic `save()`. Migration lives in `config.py` and uses only `registry.load()` / `registry.save()`, keeping the dependency one-directional (`cli → config → registry`). `registry.py` never learns that `config.py` exists.

**Tech Stack:** Python 3.11+, Click 8.1+, pytest. Standard library only beyond Click.

## Global Constraints

- **Python:** `>=3.11` per `pyproject.toml`. `X | None` union syntax is available and used.
- **Dependencies:** Runtime dependency is `click` alone. Do not add any package. `json`, `os`, `pathlib` are the only imports `config.py` needs beyond `click` and `ai.registry`.
- **Platform:** macOS. Do not add Linux or Windows branches.
- **Config path:** `~/.config/ai/config.json`, overridable via the `AI_CONFIG_PATH` environment variable.
- **Registry path:** `~/.config/ai/registry.json`, overridable via the `AI_REGISTRY_PATH` environment variable. Unchanged.
- **Atomic writes:** every save serializes to a `.tmp` sibling via `Path.with_suffix(".tmp")`, then `rename()` over the target.
- **Error message strings** are copied verbatim from this plan. They are asserted against in tests and shown to users.
- **Migration notices go to stderr** (`click.echo(..., err=True)`) so that `ai path qwen | pbcopy` stays clean.
- **Every task ends with the full suite green.** Run `.venv/bin/python -m pytest tests/ -v`, not a bare `pytest`, so the repo venv is used.
- **Out of scope:** no `ai config` subcommand, no configurable scan paths, no profile presets, no YAML.

**Reference spec:** `docs/superpowers/specs/2026-08-09-config-extraction-design.md`

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `tests/conftest.py` | Create (Task 1) | Autouse fixture redirecting both config and registry paths into `tmp_path` |
| `src/ai/config.py` | Create (Task 1), Modify (Task 2) | User settings: defaults, load, atomic save, legacy migration |
| `tests/test_config.py` | Create (Task 1), Modify (Task 2) | Coverage for the above |
| `src/ai/registry.py` | Modify (Task 2) | `_DEFAULT` shrinks to `{"models": {}}` |
| `tests/test_registry.py` | Modify (Task 2) | Drop `defaults` assertions, simplify fixture, fix a broken temp-file assertion |
| `src/ai/cli.py` | Modify (Task 2) | Four call sites read `config.load()` instead of `reg["defaults"]` |
| `ARCHITECTURE.md` | Modify (Task 2) | Document the two-file layout |

**Why only two tasks.** Task 1 is purely additive — nothing existing changes, so a reviewer can accept or reject it on its own. Task 2 cannot be subdivided: shrinking `registry._DEFAULT` makes `reg["defaults"]` raise `KeyError` on a fresh install, so the `cli.py` cutover must land in the same commit. Splitting it would leave the app broken at an intermediate commit.

---

## Task 1: Config module (no migration yet)

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`
- Create: `src/ai/config.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces, relied on by Task 2:
  - `config.DEFAULT_CONFIG: dict` — flat, seven keys, module-level constant
  - `config._path() -> pathlib.Path`
  - `config.load() -> dict`
  - `config.save(data: dict) -> None`

- [ ] **Step 1: Create the autouse isolation fixture**

Create `tests/conftest.py`:

```python
import pytest


@pytest.fixture(autouse=True)
def isolate_paths(tmp_path, monkeypatch):
    """Redirect config and registry at a temp dir for every test.

    Autouse and mandatory: config.load() *writes* to registry.json during
    migration, so a test that skipped this could rewrite the developer's real
    ~/.config/ai/registry.json. monkeypatch restores the environment on teardown.
    """
    monkeypatch.setenv("AI_REGISTRY_PATH", str(tmp_path / "registry.json"))
    monkeypatch.setenv("AI_CONFIG_PATH", str(tmp_path / "config.json"))
```

- [ ] **Step 2: Confirm the existing suite still passes with the fixture in place**

Run: `.venv/bin/python -m pytest tests/ -v`

Expected: 46 passed. The fixture sets `AI_REGISTRY_PATH` to the same value `test_registry.py`'s own `reg_path` fixture already sets, so nothing changes yet.

- [ ] **Step 3: Write the failing tests**

Create `tests/test_config.py`:

```python
import json

import click
import pytest

from ai import config


@pytest.fixture
def cfg_path(tmp_path):
    """The path conftest.isolate_paths pointed AI_CONFIG_PATH at."""
    return tmp_path / "config.json"


def test_load_creates_default_when_missing(cfg_path):
    data = config.load()
    assert data["port"] == 8083
    assert data["temp"] == 0.7
    assert data["flash_attn"] is True
    assert set(data) == set(config.DEFAULT_CONFIG)


def test_load_does_not_write_a_file_when_missing(cfg_path):
    config.load()
    assert not cfg_path.exists()


def test_load_returns_an_independent_copy(cfg_path):
    first = config.load()
    first["port"] = 1
    assert config.load()["port"] == 8083


def test_load_reads_existing(cfg_path):
    cfg_path.write_text(json.dumps({"port": 9999, "temp": 0.1}))
    data = config.load()
    assert data["port"] == 9999
    assert data["temp"] == 0.1


def test_load_corrupt_raises(cfg_path):
    cfg_path.write_text("{not valid json")
    with pytest.raises(click.ClickException):
        config.load()


def test_save_round_trips(cfg_path):
    config.save({**config.DEFAULT_CONFIG, "port": 9001})
    assert config.load()["port"] == 9001


def test_save_is_atomic(cfg_path, tmp_path):
    config.save(dict(config.DEFAULT_CONFIG))
    assert cfg_path.exists()
    assert not (tmp_path / "config.tmp").exists()
```

- [ ] **Step 4: Run the new tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`

Expected: collection error, `ImportError: cannot import name 'config' from 'ai'`. The module does not exist yet.

- [ ] **Step 5: Implement the module**

Create `src/ai/config.py`:

```python
"""User settings, kept separate from the model registry so that rebuilding the
registry with `ai scan` cannot destroy preferences."""
import json
import os
from pathlib import Path

import click

DEFAULT_CONFIG = {
    "port": 8083,
    "temp": 0.7,
    "top_p": 0.8,
    "top_k": 20,
    "min_p": 0,
    "n_gpu_layers": 99,
    "flash_attn": True,
}


def _path() -> Path:
    return Path(os.environ.get("AI_CONFIG_PATH", "~/.config/ai/config.json")).expanduser()


def load() -> dict:
    p = _path()
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        return dict(DEFAULT_CONFIG)
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        raise click.ClickException(
            f"Config file is corrupt: {p}\nDelete it to regenerate defaults."
        )


def save(data: dict) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(p)
```

`DEFAULT_CONFIG` holds only scalars, so `dict(...)` is a sufficient copy. No `deepcopy` is needed.

- [ ] **Step 6: Run the new tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`

Expected: 7 passed.

- [ ] **Step 7: Run the whole suite**

Run: `.venv/bin/python -m pytest tests/ -v`

Expected: 53 passed (46 existing + 7 new). Nothing existing has changed.

- [ ] **Step 8: Commit**

```bash
git add tests/conftest.py tests/test_config.py src/ai/config.py
git commit -m "feat: add config module for user settings"
```

---

## Task 2: Migration and cutover

**Files:**
- Modify: `src/ai/config.py` (rewrite `load()`, add `_migrate_from_registry()`)
- Modify: `tests/test_config.py` (append migration tests)
- Modify: `src/ai/registry.py:8-19` (`_DEFAULT`)
- Modify: `tests/test_registry.py` (fixture, two assertions, one dict literal, unused imports, one broken assertion)
- Modify: `src/ai/cli.py` (import line, and lines 56, 73, 94, 124)
- Modify: `ARCHITECTURE.md`

**Interfaces:**
- Consumes from Task 1: `config.DEFAULT_CONFIG`, `config._path()`, `config.load()`, `config.save(data)`.
- Consumes from existing code: `registry.load() -> dict`, `registry.save(data: dict) -> None`, `registry.merge_defaults(model: dict, defaults: dict) -> dict`.
- Produces: `config._migrate_from_registry() -> dict | None`. Returns the migrated config, or `None` when there is nothing to migrate.

- [ ] **Step 1: Shrink the registry default**

In `src/ai/registry.py`, replace the `_DEFAULT` block (lines 8-19):

```python
_DEFAULT = {
    "defaults": {
        "port": 8083,
        "temp": 0.7,
        "top_p": 0.8,
        "top_k": 20,
        "min_p": 0,
        "n_gpu_layers": 99,
        "flash_attn": True,
    },
    "models": {},
}
```

with:

```python
_DEFAULT = {"models": {}}
```

This is what makes migration detection work without a filesystem check: a missing `registry.json` now yields a dict with no `defaults` key, so `"defaults" not in reg` is a complete test for "nothing to migrate."

- [ ] **Step 2: Run the suite to see exactly what breaks**

Run: `.venv/bin/python -m pytest tests/ -v`

Expected: 2 failures in `tests/test_registry.py` — `test_load_creates_default_when_missing` (asserts `"defaults" in data`) and `test_load_reads_existing` (asserts `data["defaults"]["port"] == 9999`). Everything else still passes. These are fixed in the next step.

- [ ] **Step 3: Update the registry tests**

In `tests/test_registry.py`:

Replace the imports at lines 1-6:

```python
import json
import os
import pytest
import click
from pathlib import Path
from ai import registry
```

with (`os` and `Path` are both unused once the fixture is simplified):

```python
import json

import click
import pytest

from ai import registry
```

Replace the `reg_path` fixture:

```python
@pytest.fixture
def reg_path(tmp_path):
    p = tmp_path / "registry.json"
    os.environ["AI_REGISTRY_PATH"] = str(p)
    yield p
    del os.environ["AI_REGISTRY_PATH"]
```

with (`tests/conftest.py` now owns the environment variable):

```python
@pytest.fixture
def reg_path(tmp_path):
    """The path conftest.isolate_paths pointed AI_REGISTRY_PATH at."""
    return tmp_path / "registry.json"
```

Replace `test_load_creates_default_when_missing`:

```python
def test_load_creates_default_when_missing(reg_path):
    data = registry.load()
    assert data == {"models": {}}
```

Replace `test_load_reads_existing`:

```python
def test_load_reads_existing(reg_path):
    reg_path.write_text(json.dumps({"models": {"qwen": {"path": "/tmp/qwen.gguf"}}}))
    data = registry.load()
    assert data["models"]["qwen"]["path"] == "/tmp/qwen.gguf"
```

In `test_get_model_found`, drop the now-meaningless `"defaults": {}` key from the written dict:

```python
def test_get_model_found(reg_path):
    reg_path.write_text(json.dumps({
        "models": {"qwen": {"path": "/tmp/qwen.gguf", "ctx": 4096}}
    }))
    data = registry.load()
    m = registry.get_model(data, "qwen")
    assert m["path"] == "/tmp/qwen.gguf"
```

Fix the final assertion in `test_save_is_atomic`. `Path("registry.json").with_suffix(".tmp")` is `registry.tmp`, not `registry.json.tmp`, so the existing check tests for a file that could never exist:

```python
def test_save_is_atomic(reg_path, tmp_path):
    data = registry.load()
    registry.add_model(data, "y", {"path": "/tmp/y.gguf", "ctx": 8192})
    registry.save(data)
    assert reg_path.exists()
    # No .tmp leftover
    assert not (tmp_path / "registry.tmp").exists()
```

Leave `test_merge_defaults` untouched. It tests a pure function that does not care where defaults come from.

- [ ] **Step 4: Run the registry tests**

Run: `.venv/bin/python -m pytest tests/test_registry.py -v`

Expected: all pass.

- [ ] **Step 5: Write the failing migration tests**

Append to `tests/test_config.py`:

```python
@pytest.fixture
def reg_path(tmp_path):
    """The path conftest.isolate_paths pointed AI_REGISTRY_PATH at."""
    return tmp_path / "registry.json"


def write_legacy_registry(reg_path, defaults):
    """A pre-split registry.json: defaults and models in one file."""
    reg_path.write_text(json.dumps({
        "defaults": defaults,
        "models": {"qwen": {"path": "/tmp/qwen.gguf", "ctx": 4096}},
    }))


def test_migrates_defaults_from_registry(cfg_path, reg_path):
    write_legacy_registry(reg_path, {"port": 9999, "temp": 0.3})
    cfg = config.load()
    assert cfg["port"] == 9999
    assert cfg["temp"] == 0.3


def test_migration_writes_the_config_file(cfg_path, reg_path):
    write_legacy_registry(reg_path, {"port": 9999})
    config.load()
    assert json.loads(cfg_path.read_text())["port"] == 9999


def test_migration_strips_defaults_from_registry(cfg_path, reg_path):
    write_legacy_registry(reg_path, {"port": 9999})
    config.load()
    on_disk = json.loads(reg_path.read_text())
    assert "defaults" not in on_disk
    assert on_disk["models"]["qwen"]["path"] == "/tmp/qwen.gguf"


def test_migration_backfills_missing_fields(cfg_path, reg_path):
    write_legacy_registry(reg_path, {"port": 9999})
    cfg = config.load()
    assert cfg["port"] == 9999
    assert set(cfg) == set(config.DEFAULT_CONFIG)
    assert cfg["top_k"] == 20


def test_migration_notice_goes_to_stderr(cfg_path, reg_path, capsys):
    write_legacy_registry(reg_path, {"port": 9999})
    config.load()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Migrated defaults" in captured.err


def test_existing_config_wins_over_registry_defaults(cfg_path, reg_path):
    write_legacy_registry(reg_path, {"port": 9999})
    cfg_path.write_text(json.dumps({"port": 7777}))
    cfg = config.load()
    assert cfg["port"] == 7777
    # registry left alone — no migration ran
    assert "defaults" in json.loads(reg_path.read_text())


def test_no_migration_when_registry_missing(cfg_path, reg_path):
    assert not reg_path.exists()
    cfg = config.load()
    assert cfg == config.DEFAULT_CONFIG
    assert not cfg_path.exists()
```

- [ ] **Step 6: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_config.py -v -k "migrat"`

Expected: failures. `config.load()` currently returns `DEFAULT_CONFIG` and never looks at the registry, so `cfg["port"]` is `8083` rather than `9999`.

- [ ] **Step 7: Implement migration**

In `src/ai/config.py`, add the registry import below the existing `import click`:

```python
import click

from ai import registry
```

Replace `load()` with the version below, and add `_migrate_from_registry()` after it:

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


def _migrate_from_registry() -> dict | None:
    """Move a legacy `defaults` block out of registry.json into config.json.

    Returns None when there is nothing to migrate. A corrupt registry raises
    through registry.load() rather than being masked — the message names the
    file that actually needs fixing.
    """
    reg = registry.load()
    if "defaults" not in reg:
        return None

    legacy = reg.pop("defaults")
    cfg = {**DEFAULT_CONFIG, **legacy}

    # Config first, then strip the registry. A crash between the two leaves a
    # stale `defaults` key that the next run ignores. The reverse order would
    # lose the user's values if the config write failed.
    save(cfg)
    registry.save(reg)

    click.echo(f"Migrated defaults from registry.json to {_path()}", err=True)
    return cfg
```

- [ ] **Step 8: Run the config tests**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`

Expected: 14 passed (7 from Task 1 plus 7 migration tests).

- [ ] **Step 9: Switch the CLI call sites**

In `src/ai/cli.py`, change the import on line 10:

```python
from ai import registry, scanner, server
```

to:

```python
from ai import config, registry, scanner, server
```

Replace the body of `status` (lines 55-56). `registry.load()` was only ever used there to reach `defaults`, so it goes away:

```python
    reg = registry.load()
    actual_port = port or reg["defaults"].get("port", 8083)
```

becomes:

```python
    cfg = config.load()
    actual_port = port or cfg.get("port", 8083)
```

Apply the identical change in `stop` (lines 72-73).

In `start` (lines 86-94), keep `registry.load()` — it is still needed for `get_model` — and add the config load:

```python
    reg = registry.load()
    m = registry.get_model(reg, model)
    ...
    merged = registry.merge_defaults(m, reg["defaults"])
```

becomes:

```python
    reg = registry.load()
    cfg = config.load()
    m = registry.get_model(reg, model)
    ...
    merged = registry.merge_defaults(m, cfg)
```

Apply the same pattern in `chat` (lines 122-124):

```python
    reg = registry.load()
    cfg = config.load()
    m = registry.get_model(reg, model)
    merged = registry.merge_defaults(m, cfg)
```

- [ ] **Step 10: Verify no call site was missed**

Run: `grep -n 'defaults' src/ai/cli.py`

Expected: exactly one line, the `registry.merge_defaults` calls in `start` and `chat`. No occurrence of `reg["defaults"]` anywhere.

- [ ] **Step 11: Run the whole suite**

Run: `.venv/bin/python -m pytest tests/ -v`

Expected: 60 passed (46 existing, 14 config).

- [ ] **Step 12: Smoke test against the real registry**

The developer's live `~/.config/ai/registry.json` still has a `defaults` block, so this exercises the real migration path once.

```bash
cp ~/.config/ai/registry.json /tmp/registry-backup.json
ai status
```

Expected: a `Migrated defaults from registry.json to /Users/…/config.json` line on stderr, followed by `No server on port 8083`.

```bash
cat ~/.config/ai/config.json
grep -c defaults ~/.config/ai/registry.json
ai list
ai status
```

Expected: `config.json` holds the seven fields; `grep -c` prints `0`; `ai list` still shows `qwen` and `gemma4b`; the second `ai status` prints no migration notice because `config.json` now exists.

If anything looks wrong, restore with `cp /tmp/registry-backup.json ~/.config/ai/registry.json` and delete `~/.config/ai/config.json` before investigating.

- [ ] **Step 13: Update ARCHITECTURE.md**

In the "Data files" section, change the opening line `Both live in \`~/.config/ai/\`.` to introduce two files, replace the `registry.json` JSON sample so it starts directly with `"models"` and has no `defaults` block, and add a `config.json` sample above it:

```json
{ "port": 8083, "temp": 0.7, "top_p": 0.8, "top_k": 20,
  "min_p": 0, "n_gpu_layers": 99, "flash_attn": true }
```

Note that `config.json` is resolved through `AI_CONFIG_PATH` the same way the registry uses `AI_REGISTRY_PATH`.

In the "Trace: `ai start qwen`" section, step 4, change `registry.merge_defaults(m, reg["defaults"])` to `registry.merge_defaults(m, cfg)` and change the "Global defaults" row of the precedence table to say `config.json` rather than `defaults` block.

In the "Module map", add `config.py` as a fourth arrow off `cli.py`, described as "user settings, plus one-time migration out of the registry", and note that it is the only worker module that imports another (`registry`).

Delete the "Planned work" paragraph about config extraction, replacing it with a pointer to the remaining roadmap items (`ai init`, `ai install`, mlx-lm support).

- [ ] **Step 14: Commit**

```bash
git add src/ai/config.py src/ai/registry.py src/ai/cli.py \
        tests/test_config.py tests/test_registry.py ARCHITECTURE.md
git commit -m "feat: split user settings out of the model registry

Defaults move from registry.json into their own config.json. Existing
installs migrate automatically on first load, writing the config before
stripping the registry so an interrupted migration cannot lose settings."
```

---

## Self-Review Notes

**Spec coverage:**

| Spec section | Task |
|---|---|
| `config.json` flat, seven fields at top level | Task 1, Step 5 |
| `DEFAULT_CONFIG` public | Task 1, Step 5 |
| `_path()` with `AI_CONFIG_PATH` override | Task 1, Step 5 |
| `save()` atomic with mkdir guard | Task 1, Step 5 |
| Corrupt config error message | Task 1, Step 5 + test Step 3 |
| `registry._DEFAULT` shrinks to `{"models": {}}` | Task 2, Step 1 |
| `merge_defaults` unchanged | Task 2, Step 3 (test left untouched) |
| Dependency direction `cli → config → registry` | Task 2, Step 7 |
| Migration returns `None` when nothing to do | Task 2, Step 7 |
| Backfill from `DEFAULT_CONFIG` | Task 2, Step 7 + test Step 5 |
| Config written before registry stripped | Task 2, Step 7 (commented) |
| No filesystem existence check needed | Task 2, Step 1 (rationale) |
| Corrupt registry propagates | Task 2, Step 7 (docstring) |
| Migration notice on stderr | Task 2, Step 7 + test Step 5 |
| Four `cli.py` call sites | Task 2, Step 9 |
| Autouse `conftest.py` isolation | Task 1, Step 1 |
| Nine-plus config tests | Task 1 Step 3 (7), Task 2 Step 5 (7) |
| Four reworked registry tests | Task 2, Step 3 |

**Placeholder scan:** No TBDs. Every code step carries the literal code to write. Every run step names the exact command and expected output.

**Type consistency:** `DEFAULT_CONFIG`, `_path`, `load`, `save`, and `_migrate_from_registry` are spelled identically in Tasks 1 and 2. `registry.load` / `registry.save` / `registry.merge_defaults` match the existing signatures in `src/ai/registry.py`. The `cfg_path` and `reg_path` fixtures in `tests/test_config.py` both resolve to the same `tmp_path` children that `conftest.isolate_paths` writes into the environment.

**Deviation from spec, deliberate:** the spec listed nine config tests; this plan writes fourteen. The extra five cover the independent-copy guarantee, that `load()` writes no file on a miss, save round-tripping, that migration writes the config file, and the stderr/stdout split. All are cheap and each pins a behavior the implementation could plausibly get wrong.

**Drive-by fix, in scope because the file is already being edited:** `test_save_is_atomic` in `tests/test_registry.py` asserts against `registry.json.tmp`, but `Path.with_suffix(".tmp")` produces `registry.tmp`. The assertion can never fail as written. Task 2, Step 3 corrects it.
