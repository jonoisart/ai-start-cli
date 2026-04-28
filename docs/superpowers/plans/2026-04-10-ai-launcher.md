# AI Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pip-installable Python CLI (`ai`) with a JSON model registry, GGUF binary header parser, and llama-server process management.

**Architecture:** Click CLI dispatches to three focused modules: `registry.py` (JSON CRUD), `scanner.py` (GGUF discovery + binary header parsing), and `server.py` (llama-server process management). `cli.py` is pure wiring — no business logic. Registry lives at `~/.config/ai/registry.json`.

**Tech Stack:** Python 3.11+, Click 8.1+, stdlib only beyond click (struct, json, pathlib, urllib.request, shutil)

---

## File Map

```
ai-launcher/          ← repo root (current working dir)
├── pyproject.toml
├── Makefile
├── completions/
│   └── ai.zsh        ← stub only, not wired
├── src/
│   └── ai/
│       ├── __init__.py
│       ├── cli.py        ← click group + all commands, no logic
│       ├── registry.py   ← JSON registry CRUD
│       ├── scanner.py    ← GGUF discovery + header parsing
│       └── server.py     ← llama-server process management
└── tests/
    ├── __init__.py
    ├── test_registry.py
    ├── test_scanner.py
    └── test_server.py
```

---

## Task 1: Package scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/ai/__init__.py`
- Create: `src/ai/cli.py` (minimal click group)
- Create: `tests/__init__.py`
- Create: `completions/ai.zsh` (stub)
- Create: `Makefile`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p src/ai tests completions
touch src/ai/__init__.py tests/__init__.py
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ai-launcher"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["click>=8.1"]

[project.scripts]
ai = "ai.cli:cli"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 3: Create `src/ai/cli.py` with minimal click group**

```python
import click

@click.group()
def cli():
    """Local LLM launcher and model manager."""
    pass
```

- [ ] **Step 4: Create `completions/ai.zsh` stub**

```zsh
#compdef ai
# AI Launcher zsh completion — not yet implemented
```

- [ ] **Step 5: Create `Makefile`**

```makefile
.PHONY: dev install uninstall test

dev:
	pip3 install -e .

install:
	pip3 install .

uninstall:
	pip3 uninstall -y ai-launcher

test:
	python3 -m pytest tests/ -v
```

- [ ] **Step 6: Install in dev mode and verify**

```bash
pip3 install -e .
ai --help
```

Expected output:
```
Usage: ai [OPTIONS] COMMAND [ARGS]...

  Local LLM launcher and model manager.

Options:
  --help  Show this message and exit.
```

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml Makefile src/ tests/ completions/
git commit -m "feat: scaffold Python package with click entry point"
```

---

## Task 2: Registry module

**Files:**
- Create: `src/ai/registry.py`
- Create: `tests/test_registry.py`

### Default registry structure used throughout all tasks:

```python
DEFAULT_REGISTRY = {
    "defaults": {
        "port": 8083,
        "temp": 0.7,
        "top_p": 0.8,
        "top_k": 20,
        "min_p": 0,
        "n_gpu_layers": 99,
        "flash_attn": True,
    },
    "models": {}
}
```

- [ ] **Step 1: Write failing tests**

Create `tests/test_registry.py`:

```python
import json
import os
import pytest
from pathlib import Path
from ai import registry


@pytest.fixture
def reg_path(tmp_path):
    p = tmp_path / "registry.json"
    os.environ["AI_REGISTRY_PATH"] = str(p)
    yield p
    del os.environ["AI_REGISTRY_PATH"]


def test_load_creates_default_when_missing(reg_path):
    data = registry.load()
    assert "defaults" in data
    assert "models" in data
    assert data["defaults"]["port"] == 8083


def test_load_reads_existing(reg_path):
    reg_path.write_text(json.dumps({"defaults": {"port": 9999}, "models": {}}))
    data = registry.load()
    assert data["defaults"]["port"] == 9999


def test_get_model_found(reg_path):
    reg_path.write_text(json.dumps({
        "defaults": {},
        "models": {"qwen": {"path": "/tmp/qwen.gguf", "ctx": 4096}}
    }))
    data = registry.load()
    m = registry.get_model(data, "qwen")
    assert m["path"] == "/tmp/qwen.gguf"


def test_get_model_not_found_raises(reg_path):
    data = registry.load()
    import click
    with pytest.raises(click.ClickException):
        registry.get_model(data, "does-not-exist")


def test_add_and_remove_model(reg_path):
    data = registry.load()
    record = {"path": "/tmp/x.gguf", "ctx": 4096}
    registry.add_model(data, "x", record)
    registry.save(data)

    data2 = registry.load()
    assert "x" in data2["models"]

    registry.remove_model(data2, "x")
    registry.save(data2)

    data3 = registry.load()
    assert "x" not in data3["models"]


def test_remove_unknown_raises(reg_path):
    data = registry.load()
    import click
    with pytest.raises(click.ClickException):
        registry.remove_model(data, "ghost")


def test_merge_defaults():
    defaults = {"port": 8083, "temp": 0.7, "flash_attn": True}
    model = {"port": 9000, "ctx": 131072}
    merged = registry.merge_defaults(model, defaults)
    assert merged["port"] == 9000      # model wins
    assert merged["temp"] == 0.7      # fallback from defaults
    assert merged["flash_attn"] is True
    assert merged["ctx"] == 131072


def test_save_is_atomic(reg_path, tmp_path):
    data = registry.load()
    registry.add_model(data, "y", {"path": "/tmp/y.gguf", "ctx": 8192})
    registry.save(data)
    assert reg_path.exists()
    # No .tmp leftover
    assert not (tmp_path / "registry.json.tmp").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_registry.py -v
```

Expected: multiple `ModuleNotFoundError` or `ImportError` — `ai.registry` doesn't exist yet.

- [ ] **Step 3: Implement `src/ai/registry.py`**

```python
import json
import os
from pathlib import Path

import click

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


def _path() -> Path:
    return Path(os.environ.get("AI_REGISTRY_PATH", "~/.config/ai/registry.json")).expanduser()


def load() -> dict:
    p = _path()
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        return json.loads(json.dumps(_DEFAULT))  # deep copy
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        raise click.ClickException(
            f"Registry file is corrupt: {p}\nDelete it and run 'ai scan' to rebuild."
        )


def save(data: dict) -> None:
    p = _path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(p)


def get_model(data: dict, name: str) -> dict:
    m = data["models"].get(name)
    if m is None:
        raise click.ClickException(
            f"Unknown model '{name}'. Run 'ai list' to see available models."
        )
    return m


def add_model(data: dict, nickname: str, record: dict) -> None:
    data["models"][nickname] = record


def remove_model(data: dict, nickname: str) -> None:
    if nickname not in data["models"]:
        raise click.ClickException(
            f"Unknown model '{nickname}'. Run 'ai list' to see available models."
        )
    del data["models"][nickname]


def merge_defaults(model: dict, defaults: dict) -> dict:
    merged = dict(defaults)
    merged.update(model)
    return merged
```

- [ ] **Step 4: Run tests — all must pass**

```bash
python3 -m pytest tests/test_registry.py -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/ai/registry.py tests/test_registry.py
git commit -m "feat: add registry module with JSON CRUD and atomic save"
```

---

## Task 3: GGUF header parser

**Files:**
- Create: `src/ai/scanner.py` (parse functions only — discovery added in Task 4)
- Create: `tests/test_scanner.py`

The GGUF binary format (v3):
- Bytes 0–3: magic `GGUF`
- Bytes 4–7: version (uint32 LE)
- Bytes 8–15: tensor count (uint64 LE; uint32 in v1)
- Bytes 16–23: KV count (uint64 LE; uint32 in v1)
- Then KV pairs: `[key_len:u64][key:bytes][value_type:u32][value]`
- Value types: 0=u8, 1=i8, 2=u16, 3=i16, 4=u32, 5=i32, 6=f32, 7=bool, 8=string, 9=array, 10=u64, 11=i64, 12=f64
- Strings: `[len:u64][bytes]` (v2+), `[len:u32][bytes]` (v1)
- Arrays: `[elem_type:u32][count:u64][elements]` (v2+), count is u32 in v1
- `general.file_type` uint32 values → quant name map (see FILE_TYPE_NAMES below)

- [ ] **Step 1: Write failing tests**

Create `tests/test_scanner.py`:

```python
import struct
import pytest
from pathlib import Path
from ai import scanner


# --- helpers ---

def gguf_v3(metadata: list) -> bytes:
    """
    Build a minimal valid GGUF v3 byte sequence.
    metadata: list of (key, value_type, value)
      value_type 4=uint32, 8=string, 10=uint64
    """
    buf = b"GGUF"
    buf += struct.pack("<I", 3)               # version 3
    buf += struct.pack("<Q", 0)               # tensor count
    buf += struct.pack("<Q", len(metadata))   # kv count
    for key, vtype, value in metadata:
        key_b = key.encode()
        buf += struct.pack("<Q", len(key_b)) + key_b
        buf += struct.pack("<I", vtype)
        if vtype == 8:
            val_b = value.encode()
            buf += struct.pack("<Q", len(val_b)) + val_b
        elif vtype == 4:
            buf += struct.pack("<I", value)
        elif vtype == 10:
            buf += struct.pack("<Q", value)
    return buf


# --- parse_gguf_header ---

def test_parse_returns_empty_for_non_gguf(tmp_path):
    f = tmp_path / "fake.gguf"
    f.write_bytes(b"NOT_GGUF_DATA")
    assert scanner.parse_gguf_header(f) == {}


def test_parse_returns_empty_for_missing_file(tmp_path):
    assert scanner.parse_gguf_header(tmp_path / "nope.gguf") == {}


def test_parse_extracts_arch(tmp_path):
    data = gguf_v3([("general.architecture", 8, "qwen2")])
    f = tmp_path / "model.gguf"
    f.write_bytes(data)
    result = scanner.parse_gguf_header(f)
    assert result["arch"] == "qwen2"


def test_parse_extracts_quant(tmp_path):
    # general.file_type = 7 → Q8_0
    data = gguf_v3([
        ("general.architecture", 8, "llama"),
        ("general.file_type", 4, 7),
    ])
    f = tmp_path / "model.gguf"
    f.write_bytes(data)
    result = scanner.parse_gguf_header(f)
    assert result["quant"] == "Q8_0"


def test_parse_extracts_ctx(tmp_path):
    data = gguf_v3([
        ("general.architecture", 8, "qwen2"),
        ("qwen2.context_length", 4, 131072),
    ])
    f = tmp_path / "model.gguf"
    f.write_bytes(data)
    result = scanner.parse_gguf_header(f)
    assert result["ctx"] == 131072


def test_parse_extracts_params(tmp_path):
    data = gguf_v3([
        ("general.architecture", 8, "llama"),
        ("general.parameter_count", 10, 7_000_000_000),
    ])
    f = tmp_path / "model.gguf"
    f.write_bytes(data)
    result = scanner.parse_gguf_header(f)
    assert result["params"] == "7B"


def test_parse_skips_array_values(tmp_path):
    # Array of uint32 followed by a real key we care about
    array_block = struct.pack("<I", 4)   # elem type uint32
    array_block += struct.pack("<Q", 3)  # 3 elements
    array_block += struct.pack("<III", 1, 2, 3)

    buf = b"GGUF"
    buf += struct.pack("<I", 3)   # version
    buf += struct.pack("<Q", 0)   # tensor count
    buf += struct.pack("<Q", 2)   # 2 kv entries

    # Entry 1: array
    key = b"some.array"
    buf += struct.pack("<Q", len(key)) + key
    buf += struct.pack("<I", 9)   # array type
    buf += array_block

    # Entry 2: real key
    key2 = b"general.architecture"
    buf += struct.pack("<Q", len(key2)) + key2
    buf += struct.pack("<I", 8)   # string type
    arch = b"gemma3"
    buf += struct.pack("<Q", len(arch)) + arch

    f = tmp_path / "model.gguf"
    f.write_bytes(buf)
    result = scanner.parse_gguf_header(f)
    assert result["arch"] == "gemma3"


# --- nickname_from_filename ---

def test_nickname_strips_quant_suffix():
    p = Path("Qwen3.5-9B-Uncensored-Q8_0.gguf")
    nick = scanner.nickname_from_filename(p)
    assert "q8" not in nick.lower()
    assert nick.startswith("qwen")


def test_nickname_is_lowercase_hyphenated():
    p = Path("Mistral_7B_Instruct_Q4_K_M.gguf")
    nick = scanner.nickname_from_filename(p)
    assert nick == nick.lower()
    assert "_" not in nick


def test_nickname_max_32_chars():
    p = Path("very-long-model-name-that-exceeds-normal-length-Q4_K_M.gguf")
    nick = scanner.nickname_from_filename(p)
    assert len(nick) <= 32
```

- [ ] **Step 2: Run to confirm failures**

```bash
python3 -m pytest tests/test_scanner.py -v
```

Expected: `ImportError` — `ai.scanner` doesn't exist yet.

- [ ] **Step 3: Implement `src/ai/scanner.py`** (parser + nickname only; discovery in Task 4)

```python
import re
import struct
from pathlib import Path

FILE_TYPE_NAMES = {
    0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1",
    7: "Q8_0", 8: "Q5_0", 9: "Q5_1",
    10: "Q2_K", 11: "Q3_K_S", 12: "Q3_K_M", 13: "Q3_K_L",
    14: "Q4_K_S", 15: "Q4_K_M", 16: "Q5_K_S", 17: "Q5_K_M",
    18: "Q6_K", 19: "IQ2_XXS", 20: "IQ2_XS",
    28: "IQ4_NL", 29: "IQ3_S", 30: "IQ3_M",
    31: "IQ1_S", 32: "IQ4_XS",
}

GGUF_MAGIC = b"GGUF"

# Scalar value type → (struct_fmt, byte_size)
_SCALAR_FMT = {
    0: ("<B", 1), 1: ("<b", 1), 2: ("<H", 2), 3: ("<h", 2),
    4: ("<I", 4), 5: ("<i", 4), 6: ("<f", 4), 7: ("<B", 1),
    10: ("<Q", 8), 11: ("<q", 8), 12: ("<d", 8),
}


def _read_str(f, version: int) -> str:
    length = struct.unpack("<I" if version == 1 else "<Q", f.read(4 if version == 1 else 8))[0]
    return f.read(length).decode("utf-8", errors="replace")


def _skip_array(f, version: int) -> None:
    elem_type = struct.unpack("<I", f.read(4))[0]
    count = struct.unpack("<I" if version == 1 else "<Q", f.read(4 if version == 1 else 8))[0]
    if elem_type in _SCALAR_FMT:
        _, size = _SCALAR_FMT[elem_type]
        f.seek(count * size, 1)
    elif elem_type == 8:  # array of strings
        for _ in range(count):
            slen = struct.unpack("<I" if version == 1 else "<Q", f.read(4 if version == 1 else 8))[0]
            f.seek(slen, 1)
    # nested arrays (type 9) are extremely rare — ignore, parser will bail gracefully


def _read_scalar(f, value_type: int, version: int):
    if value_type == 8:
        return _read_str(f, version)
    fmt, size = _SCALAR_FMT[value_type]
    return struct.unpack(fmt, f.read(size))[0]


def parse_gguf_header(path: Path) -> dict:
    """
    Read GGUF binary header and return {arch, quant, ctx, params}.
    Returns {} on any parse failure.
    """
    try:
        with open(path, "rb") as f:
            if f.read(4) != GGUF_MAGIC:
                return {}

            version = struct.unpack("<I", f.read(4))[0]
            int_fmt = "<I" if version == 1 else "<Q"
            int_size = 4 if version == 1 else 8

            f.read(int_size)  # tensor count — skip
            kv_count = struct.unpack(int_fmt, f.read(int_size))[0]

            result = {}
            arch = None

            for _ in range(kv_count):
                key = _read_str(f, version)
                value_type = struct.unpack("<I", f.read(4))[0]

                if value_type == 9:  # array — skip
                    _skip_array(f, version)
                    continue

                value = _read_scalar(f, value_type, version)

                if key == "general.architecture":
                    arch = value
                    result["arch"] = arch
                elif key == "general.file_type":
                    result["quant"] = FILE_TYPE_NAMES.get(value, f"type_{value}")
                elif key == "general.parameter_count":
                    result["params"] = _format_params(value)
                elif key.endswith(".context_length"):
                    result["ctx"] = value

                # Stop once we have all four fields
                if len(result) == 4:
                    break

        return result
    except Exception:
        return {}


def _format_params(count: int) -> str:
    if count >= 1_000_000_000:
        return f"{count / 1_000_000_000:.0f}B"
    if count >= 1_000_000:
        return f"{count / 1_000_000:.0f}M"
    return str(count)


def nickname_from_filename(path: Path) -> str:
    stem = path.stem
    # Cut at quantization pattern (e.g. -Q8_0, _Q4_K_M)
    m = re.search(r"[-_][Qq][0-9]", stem)
    if m:
        stem = stem[: m.start()]
    nick = re.sub(r"[^a-zA-Z0-9]+", "-", stem).lower().strip("-")
    return nick[:32]
```

- [ ] **Step 4: Run tests — all must pass**

```bash
python3 -m pytest tests/test_scanner.py -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/ai/scanner.py tests/test_scanner.py
git commit -m "feat: add GGUF binary header parser and nickname helper"
```

---

## Task 4: GGUF file discovery

**Files:**
- Modify: `src/ai/scanner.py` (add `find_ggufs`, `is_registered`, `DEFAULT_SCAN_PATHS`)
- Modify: `tests/test_scanner.py` (add discovery tests)

- [ ] **Step 1: Append failing tests to `tests/test_scanner.py`**

```python
# --- find_ggufs ---

def test_find_ggufs_finds_gguf_files(tmp_path):
    (tmp_path / "model.gguf").write_bytes(b"x")
    (tmp_path / "other.txt").write_bytes(b"x")
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "deep.gguf").write_bytes(b"x")
    results = scanner.find_ggufs(str(tmp_path), depth=5)
    names = {p.name for p in results}
    assert "model.gguf" in names
    assert "deep.gguf" in names
    assert "other.txt" not in names


def test_find_ggufs_respects_depth(tmp_path):
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    (deep / "buried.gguf").write_bytes(b"x")
    results = scanner.find_ggufs(str(tmp_path), depth=2)
    names = {p.name for p in results}
    assert "buried.gguf" not in names


def test_find_ggufs_returns_empty_for_missing_path():
    results = scanner.find_ggufs("/nonexistent/path/xyz", depth=5)
    assert results == []


# --- is_registered ---

def test_is_registered_true(tmp_path):
    f = tmp_path / "model.gguf"
    f.write_bytes(b"x")
    reg = {"models": {"qwen": {"path": str(f)}}}
    assert scanner.is_registered(f, reg) is True


def test_is_registered_false(tmp_path):
    f = tmp_path / "model.gguf"
    f.write_bytes(b"x")
    reg = {"models": {}}
    assert scanner.is_registered(f, reg) is False
```

- [ ] **Step 2: Run to confirm new tests fail**

```bash
python3 -m pytest tests/test_scanner.py -v -k "find_ggufs or is_registered"
```

Expected: `AttributeError` — functions not defined yet.

- [ ] **Step 3: Add discovery functions to `src/ai/scanner.py`**

Append to the bottom of `scanner.py` (after the existing functions):

```python
from pathlib import Path
import os

DEFAULT_SCAN_PATHS = [
    "~/.cache/huggingface/hub",
    "~/.cache/llama.cpp",
    "~/Downloads",
    "/Volumes",
]


def find_ggufs(path: str, depth: int = 5) -> list:
    root = Path(path).expanduser()
    if not root.exists():
        return []
    return _walk(root, depth)


def _walk(directory: Path, depth: int) -> list:
    if depth < 0:
        return []
    results = []
    try:
        for entry in directory.iterdir():
            if entry.is_file() and entry.suffix.lower() == ".gguf":
                results.append(entry)
            elif entry.is_dir() and not entry.is_symlink():
                results.extend(_walk(entry, depth - 1))
    except PermissionError:
        pass
    return results


def is_registered(path: Path, registry: dict) -> bool:
    registered_paths = {m["path"] for m in registry.get("models", {}).values()}
    return str(path) in registered_paths
```

- [ ] **Step 4: Run all scanner tests**

```bash
python3 -m pytest tests/test_scanner.py -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/ai/scanner.py tests/test_scanner.py
git commit -m "feat: add GGUF file discovery with depth-limited walk"
```

---

## Task 5: Server module

**Files:**
- Create: `src/ai/server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_server.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from ai import server


MODEL = {
    "path": "/tmp/model.gguf",
    "ctx": 131072,
    "port": 8083,
    "temp": 0.7,
    "top_p": 0.8,
    "top_k": 20,
    "min_p": 0,
    "n_gpu_layers": 99,
    "flash_attn": True,
    "reasoning": False,
    "jinja": True,
}


# --- build_argv ---

def test_build_argv_includes_model_path():
    argv = server.build_argv(MODEL)
    assert "-m" in argv
    assert "/tmp/model.gguf" in argv


def test_build_argv_includes_ctx():
    argv = server.build_argv(MODEL)
    assert "-c" in argv
    assert "131072" in argv


def test_build_argv_flash_attn_on():
    argv = server.build_argv(MODEL)
    assert "-fa" in argv
    assert "on" in argv


def test_build_argv_flash_attn_off():
    m = {**MODEL, "flash_attn": False}
    argv = server.build_argv(m)
    assert "-fa" not in argv


def test_build_argv_reasoning_off():
    argv = server.build_argv(MODEL)
    assert "--reasoning-format" in argv
    assert "none" in argv


def test_build_argv_reasoning_on():
    m = {**MODEL, "reasoning": True}
    argv = server.build_argv(m)
    assert "--reasoning-format" not in argv


def test_build_argv_jinja_true():
    argv = server.build_argv(MODEL)
    assert "--jinja" in argv


def test_build_argv_jinja_false():
    m = {**MODEL, "jinja": False}
    argv = server.build_argv(m)
    assert "--jinja" not in argv


# --- find_llama_server ---

def test_find_llama_server_found():
    with patch("shutil.which", return_value="/opt/homebrew/bin/llama-server"):
        assert server.find_llama_server() == "/opt/homebrew/bin/llama-server"


def test_find_llama_server_not_found_raises():
    import click
    with patch("shutil.which", return_value=None):
        with pytest.raises(click.ClickException, match="brew install llama.cpp"):
            server.find_llama_server()


# --- stop ---

def test_stop_kills_process():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="12345\n", returncode=0)
        with patch("os.kill") as mock_kill:
            server.stop(8083)
            mock_kill.assert_called_once_with(12345, 15)  # SIGTERM


def test_stop_no_process_prints_message(capsys):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", returncode=1)
        server.stop(8083)
        captured = capsys.readouterr()
        assert "No server" in captured.out


# --- status ---

def test_status_running():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="12345\n", returncode=0)
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.read.return_value = b'{"status":"ok"}'
            mock_urlopen.return_value = mock_resp
            result = server.status(8083)
            assert result["running"] is True
            assert result["pid"] == 12345


def test_status_not_running():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", returncode=1)
        result = server.status(8083)
        assert result["running"] is False
```

- [ ] **Step 2: Run to confirm failures**

```bash
python3 -m pytest tests/test_server.py -v
```

Expected: `ImportError` — `ai.server` doesn't exist yet.

- [ ] **Step 3: Create `src/ai/server.py`**

```python
import json
import os
import shutil
import signal
import subprocess
import urllib.request
from pathlib import Path

import click


def find_llama_server() -> str:
    binary = shutil.which("llama-server")
    if not binary:
        raise click.ClickException(
            "llama-server not found. Install with: brew install llama.cpp"
        )
    return binary


def build_argv(model: dict) -> list:
    binary = find_llama_server()
    argv = [
        binary,
        "-m", model["path"],
        "-c", str(model["ctx"]),
        "--port", str(model.get("port", 8083)),
        "--temp", str(model.get("temp", 0.7)),
        "--top-p", str(model.get("top_p", 0.8)),
        "--top-k", str(model.get("top_k", 20)),
        "--min-p", str(model.get("min_p", 0)),
        "-ngl", str(model.get("n_gpu_layers", 99)),
        "--embeddings", str(model.get("embeddings", True)),
        "--pooling", str(model.get("pooling", "mean")),
    ]
    if model.get("flash_attn", True):
        argv += ["-fa", "on"]
    if not model.get("reasoning", True):
        argv += ["--reasoning-format", "none"]
    if model.get("jinja", False):
        argv.append("--jinja")
    return argv


def start(argv: list) -> None:
    """Replace current process with llama-server."""
    os.execvp(argv[0], argv)


def _get_pid(port: int) -> int | None:
    result = subprocess.run(
        ["lsof", "-ti", f"tcp:{port}"],
        capture_output=True, text=True
    )
    pid_str = result.stdout.strip()
    return int(pid_str) if pid_str else None


def stop(port: int) -> None:
    pid = _get_pid(port)
    if pid:
        os.kill(pid, signal.SIGTERM)
        click.echo(f"Stopped server on port {port} (PID {pid})")
    else:
        click.echo(f"No server running on port {port}")


def status(port: int) -> dict:
    pid = _get_pid(port)
    if not pid:
        return {"running": False}

    try:
        with urllib.request.urlopen(
            f"http://localhost:{port}/health", timeout=2
        ) as resp:
            data = json.loads(resp.read())
            return {"running": True, "pid": pid, "health": data}
    except Exception:
        return {"running": True, "pid": pid, "health": None}
```

- [ ] **Step 4: Run tests — all must pass**

```bash
python3 -m pytest tests/test_server.py -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/ai/server.py tests/test_server.py
git commit -m "feat: add server module for llama-server process management"
```

---

## Task 6: CLI — read-only commands + start

**Files:**
- Modify: `src/ai/cli.py`

All commands wired here. No logic — everything delegates to modules.

- [ ] **Step 1: Replace `src/ai/cli.py` with the full implementation**

```python
import json
import urllib.request
from datetime import date

import click

from ai import registry, scanner, server


@click.group()
def cli():
    """Local LLM launcher and model manager."""
    pass


# ── list ──────────────────────────────────────────────────────────────────────

@cli.command("list")
def list_models():
    """Show all registered models."""
    reg = registry.load()
    models = reg.get("models", {})
    if not models:
        click.echo("No models registered. Run 'ai scan' to discover models.")
        return
    click.echo(f"{'NICKNAME':<16} {'NAME':<35} {'QUANT':<10} {'PARAMS':<8} {'CTX':<8} PATH")
    click.echo("-" * 110)
    for nick, m in sorted(models.items()):
        click.echo(
            f"{nick:<16} {m.get('name', ''):<35} {m.get('quant', '?'):<10} "
            f"{m.get('params', '?'):<8} {m.get('ctx', '?'):<8} {m.get('path', '')}"
        )


# ── path ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("model")
def path(model):
    """Print model file path."""
    reg = registry.load()
    m = registry.get_model(reg, model)
    click.echo(m["path"])


# ── status ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--port", default=None, type=int, help="Port to check (default: registry default)")
def status(port):
    """Check if a server is running."""
    reg = registry.load()
    actual_port = port or reg["defaults"].get("port", 8083)
    s = server.status(actual_port)
    if s["running"]:
        click.echo(f"Server running on port {actual_port} (PID {s['pid']})")
        if s.get("health"):
            click.echo(f"Health: {s['health']}")
    else:
        click.echo(f"No server on port {actual_port}")


# ── stop ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--port", default=None, type=int, help="Port to stop (default: registry default)")
def stop(port):
    """Stop a running server."""
    reg = registry.load()
    actual_port = port or reg["defaults"].get("port", 8083)
    server.stop(actual_port)


# ── start ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("model")
@click.option("--ctx", default=None, type=int, help="Context window size")
@click.option("--port", default=None, type=int, help="Port to serve on")
@click.option("--temp", default=None, type=float, help="Temperature")
def start(model, ctx, port, temp):
    """Start a model server (foreground)."""
    reg = registry.load()
    m = registry.get_model(reg, model)

    if not __import__("pathlib").Path(m["path"]).exists():
        raise click.ClickException(
            f"Model file not found: {m['path']}\nRe-run 'ai scan' or 'ai add'."
        )

    merged = registry.merge_defaults(m, reg["defaults"])
    if ctx is not None:
        merged["ctx"] = ctx
    if port is not None:
        merged["port"] = port
    if temp is not None:
        merged["temp"] = temp

    actual_port = merged.get("port", 8083)
    existing_pid = server._get_pid(actual_port)
    if existing_pid:
        raise click.ClickException(
            f"Port {actual_port} in use (PID {existing_pid}). Run 'ai stop --port {actual_port}' first."
        )

    click.echo(f"Starting {m.get('name', model)} on port {actual_port}...")
    argv = server.build_argv(merged)
    server.start(argv)


# ── chat ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("model")
@click.argument("message", default=None, required=False)
@click.option("--port", default=None, type=int)
def chat(model, message, port):
    """Send a message to a running model server."""
    reg = registry.load()
    m = registry.get_model(reg, model)
    merged = registry.merge_defaults(m, reg["defaults"])
    actual_port = port or merged.get("port", 8083)

    if not server._get_pid(actual_port):
        raise click.ClickException(
            f"No server on port {actual_port}. Start with: ai start {model}"
        )

    if not message:
        message = click.get_text_stream("stdin").read().strip()

    payload = json.dumps({
        "model": "local",
        "messages": [{"role": "user", "content": message}],
        "temperature": merged.get("temp", 0.7),
    }).encode()

    req = urllib.request.Request(
        f"http://localhost:{actual_port}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            click.echo(data["choices"][0]["message"]["content"])
    except Exception as e:
        raise click.ClickException(f"Request failed: {e}")


# ── scan ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("path", default=None, required=False)
@click.option("--depth", default=5, type=int, show_default=True, help="Directory scan depth")
@click.option("--auto", is_flag=True, help="Add all found models without prompting")
def scan(path, depth, auto):
    """Discover GGUF files and add them to the registry."""
    reg = registry.load()
    search_paths = [path] if path else scanner.DEFAULT_SCAN_PATHS

    click.echo("Scanning for GGUF models...")
    found = []
    for p in search_paths:
        found.extend(scanner.find_ggufs(p, depth))

    new_files = [f for f in found if not scanner.is_registered(f, reg)]

    if not new_files:
        click.echo("No new models found.")
        return

    click.echo(f"Found {len(new_files)} new model(s):\n")
    added = 0

    for gguf_path in new_files:
        meta = scanner.parse_gguf_header(gguf_path)
        click.echo(f"  {gguf_path}")
        if meta:
            click.echo(
                f"  Arch: {meta.get('arch', '?')}  "
                f"Quant: {meta.get('quant', '?')}  "
                f"Params: {meta.get('params', '?')}  "
                f"Ctx: {meta.get('ctx', '?')}"
            )
        else:
            click.echo("  (could not parse metadata — filename heuristics only)")

        if not auto and not click.confirm("  Add to registry?", default=True):
            click.echo()
            continue

        default_nick = scanner.nickname_from_filename(gguf_path)
        default_name = gguf_path.stem

        if auto:
            nickname = default_nick
            display_name = default_name
        else:
            nickname = click.prompt("  Nickname", default=default_nick)
            display_name = click.prompt("  Display name", default=default_name)

        ctx = meta.get("ctx")
        if not ctx:
            ctx = click.prompt("  Context length", type=int, default=4096)

        reasoning = False
        jinja = False
        if not auto:
            reasoning = click.confirm("  Enable reasoning output?", default=False)
            jinja = click.confirm("  Use Jinja chat template?", default=False)

        record = {
            "path": str(gguf_path),
            "name": display_name,
            "arch": meta.get("arch", "unknown"),
            "quant": meta.get("quant", "unknown"),
            "params": meta.get("params", "unknown"),
            "ctx": ctx,
            "reasoning": reasoning,
            "jinja": jinja,
            "added": date.today().isoformat(),
        }
        if not meta:
            record["unverified"] = True

        registry.add_model(reg, nickname, record)
        click.echo(f"  Added '{nickname}'\n")
        added += 1

    if added:
        registry.save(reg)
        click.echo(f"Registry updated. Run 'ai list' to see all models.")


# ── add ───────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("path")
@click.argument("nickname")
def add(path, nickname):
    """Manually register a GGUF model file."""
    from pathlib import Path as _Path
    gguf_path = _Path(path).expanduser().resolve()
    if not gguf_path.exists():
        raise click.ClickException(f"File not found: {gguf_path}")
    if gguf_path.suffix.lower() != ".gguf":
        raise click.ClickException(f"Expected a .gguf file, got: {gguf_path.name}")

    reg = registry.load()
    meta = scanner.parse_gguf_header(gguf_path)

    click.echo(f"File: {gguf_path}")
    if meta:
        click.echo(f"Detected — Arch: {meta.get('arch','?')}  Quant: {meta.get('quant','?')}  Params: {meta.get('params','?')}  Ctx: {meta.get('ctx','?')}")
    else:
        click.echo("Could not parse metadata — please fill in manually.")

    display_name = click.prompt("Display name", default=gguf_path.stem)
    ctx = meta.get("ctx") or click.prompt("Context length", type=int, default=4096)
    reasoning = click.confirm("Enable reasoning output?", default=False)
    jinja = click.confirm("Use Jinja chat template?", default=False)

    record = {
        "path": str(gguf_path),
        "name": display_name,
        "arch": meta.get("arch", "unknown"),
        "quant": meta.get("quant", "unknown"),
        "params": meta.get("params", "unknown"),
        "ctx": ctx,
        "reasoning": reasoning,
        "jinja": jinja,
        "added": date.today().isoformat(),
    }
    if not meta:
        record["unverified"] = True

    registry.add_model(reg, nickname, record)
    registry.save(reg)
    click.echo(f"Added '{nickname}'")


# ── remove ────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("nickname")
def remove(nickname):
    """Remove a model from the registry (does not delete the file)."""
    reg = registry.load()
    registry.remove_model(reg, nickname)
    registry.save(reg)
    click.echo(f"Removed '{nickname}' from registry.")
```

- [ ] **Step 2: Verify all commands appear in help**

```bash
ai --help
```

Expected output includes: `list`, `path`, `status`, `stop`, `start`, `chat`, `scan`, `add`, `remove`.

- [ ] **Step 3: Smoke test read-only commands against empty registry**

```bash
ai list
ai status
```

Expected:
```
No models registered. Run 'ai scan' to discover models.
No server on port 8083
```

- [ ] **Step 4: Commit**

```bash
git add src/ai/cli.py
git commit -m "feat: wire all CLI commands via click"
```

---

## Task 7: Seed registry with existing models

**Files:**
- No code changes — run `ai add` for each existing model

- [ ] **Step 1: Add qwen**

```bash
ai add "/Users/onoi/.cache/huggingface/hub/models--HauhauCS--Qwen3.5-9B-Uncensored-HauhauCS-Aggressive/snapshots/335e9ef38ada3edf9f9a3a6c2836022c1ab76ea1/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q8_0.gguf" qwen
```

When prompted:
- Display name: `Qwen 3.5 9B Uncensored (Q8_0)`
- Context length: (should auto-detect; if not, enter `131072`)
- Enable reasoning output? `n`
- Use Jinja chat template? `y`

- [ ] **Step 2: Add gemma**

```bash
ai add "/Users/onoi/.cache/huggingface/hub/models--HauhauCS--Gemma-4-E4B-Uncensored-HauhauCS-Aggressive/snapshots/45b6a334b4bcd1d7f37179df58b3b1d66a184e5d/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf" gemma
```

When prompted:
- Display name: `Gemma 4 Uncensored (Q4_K_M)`
- Context length: (auto-detect; if not, `131072`)
- Enable reasoning output? `n`
- Use Jinja chat template? `n`

- [ ] **Step 3: Add gemma-base**

```bash
ai add "/Users/onoi/.cache/huggingface/hub/models--unsloth--gemma-4-E4B-it-GGUF/snapshots/315e03409eb1cdde302488d66e586dea1e82aad1/gemma-4-E4B-it-Q8_0.gguf" gemma-base
```

When prompted:
- Display name: `Gemma 4 Instruct (Q8_0)`
- Context length: (auto-detect; if not, `131072`)
- Enable reasoning output? `n`
- Use Jinja chat template? `n`

- [ ] **Step 4: Verify registry**

```bash
ai list
```

Expected: table showing qwen, gemma, gemma-base with their metadata.

- [ ] **Step 5: Smoke test start (dry run — will actually launch server)**

```bash
ai start qwen --port 8084
```

Verify llama-server launches with the expected flags. `Ctrl+C` to stop.

- [ ] **Step 6: Commit**

```bash
git add -p  # nothing to stage — registry.json is in ~/.config, not the repo
git commit -m "feat: complete AI Launcher MVP — registry seeded and all commands working" --allow-empty
```

> Note: `~/.config/ai/registry.json` is outside the repo — it's a user config file, not committed. If you want to version it, copy it to the repo as `config/registry.example.json` manually.

---

## Self-Review Notes

**Spec coverage check:**
- `ai start` ✅ Task 6
- `ai stop` ✅ Task 6
- `ai status` ✅ Task 6
- `ai list` ✅ Task 6
- `ai path` ✅ Task 6
- `ai chat` ✅ Task 6
- `ai scan` ✅ Task 6
- `ai add` ✅ Task 6
- `ai remove` ✅ Task 6
- GGUF header parsing ✅ Task 3
- File discovery ✅ Task 4
- JSON registry ✅ Task 2
- Per-model ctx ✅ registry schema + merge_defaults
- `reasoning`/`jinja` per-model flags ✅ build_argv tests
- Atomic registry save ✅ registry.save
- Error messages match spec ✅ all ClickException messages match spec table
- `lsof` macOS dependency ✅ server._get_pid
- `jq` NOT required ✅ urllib.request used for chat
- Out-of-scope items not included ✅

**Type/name consistency check:**
- `registry.get_model(data, name)` — used consistently in cli.py ✅
- `registry.merge_defaults(model, defaults)` — used in `start` and `chat` ✅
- `server._get_pid(port)` — used in `start` and `chat` (internal function, prefixed `_`) ✅
- `server.start(argv)` — called in cli `start` command ✅
- `scanner.find_ggufs(path, depth)` — called in `scan` command ✅
- `scanner.is_registered(path, reg)` — called in `scan` command ✅
- `scanner.parse_gguf_header(path)` — called in `scan` and `add` ✅
- `scanner.nickname_from_filename(path)` — called in `scan` ✅
