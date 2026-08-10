"""llama-server process management."""
import json
import os
import shutil
import signal
import subprocess
import urllib.error
import urllib.request

import click


# KV cache types that llama.cpp will only accept alongside flash attention.
# f16/f32/bf16 are unquantized and work either way.
_QUANTIZED_CACHE_TYPES = {"q8_0", "q5_1", "q5_0", "q4_1", "q4_0", "iq4_nl"}


def find_llama_server() -> str:
    binary = shutil.which("llama-server")
    if not binary:
        raise click.ClickException(
            "llama-server not found. Install with: brew install llama.cpp"
        )
    return binary


def build_argv(model: dict) -> list:
    path = model.get("path")
    ctx = model.get("ctx")
    if not path:
        raise click.ClickException("Model record missing 'path'. Re-run 'ai scan' or 'ai add'.")
    if not ctx:
        raise click.ClickException("Model record missing 'ctx'. Re-run 'ai add' to set context size.")
    binary = find_llama_server()
    argv = [
        binary,
        "-m", path,
        "-c", str(ctx),
        "--port", str(model.get("port", 8083)),
        "--temp", str(model.get("temp", 0.7)),
        "--top-p", str(model.get("top_p", 0.8)),
        "--top-k", str(model.get("top_k", 20)),
        "--min-p", str(model.get("min_p", 0)),
        "-ngl", str(model.get("n_gpu_layers", 99)),
    ]
    cache_k = model.get("cache_type_k")
    cache_v = model.get("cache_type_v")
    if not model.get("flash_attn", True):
        for value in (cache_k, cache_v):
            if value in _QUANTIZED_CACHE_TYPES:
                raise click.ClickException(
                    f"Cache type '{value}' requires flash attention. "
                    "Set flash_attn to true, or use an unquantized cache type."
                )
    if cache_k:
        argv += ["-ctk", cache_k]
    if cache_v:
        argv += ["-ctv", cache_v]

    if model.get("flash_attn", True):
        argv += ["-fa", "on"]
    if not model.get("reasoning", True):
        argv += ["--reasoning-format", "none"]
    if model.get("jinja", False):
        argv.append("--jinja")
    if model.get("name"):
        argv += ["--alias", model["name"]]
    # Both opt-in. Embedding models declare pooling_type in their GGUF header
    # (Qwen3-Embedding declares LAST); passing --pooling overrides that, and a
    # wrong pooling still returns correctly-sized vectors, so the damage is
    # silent. Only send it when a model explicitly asks for one.
    if model.get("embeddings", False):
        argv.append("--embeddings")
    if model.get("pooling"):
        argv += ["--pooling", model["pooling"]]
    return argv


def start(argv: list) -> None:
    """Replace current process with llama-server (never returns)."""
    os.execvp(argv[0], argv)


def get_pid(port: int) -> int | None:
    # -sTCP:LISTEN targets only the listening socket — avoids multi-PID output
    # from established client connections on the same port
    result = subprocess.run(
        ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
        capture_output=True, text=True
    )
    pid_str = result.stdout.strip()
    return int(pid_str) if pid_str else None


_get_pid = get_pid  # backward compat for existing tests


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
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return {"running": True, "pid": pid, "health": None}
