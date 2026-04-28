"""AI Launcher CLI — thin dispatch layer. No business logic here."""
import json
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

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

    if not Path(m["path"]).exists():
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
    existing_pid = server.get_pid(actual_port)
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

    if not server.get_pid(actual_port):
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
    except urllib.error.HTTPError as e:
        raise click.ClickException(f"Server returned HTTP {e.code}: {e.reason}")
    except (urllib.error.URLError, OSError) as e:
        raise click.ClickException(f"Connection failed: {e.reason}")
    except (json.JSONDecodeError, KeyError):
        raise click.ClickException("Server returned unexpected response format.")


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
    input_path = Path(path).expanduser()
    if input_path.suffix.lower() != ".gguf":
        raise click.ClickException(f"Expected a .gguf file, got: {input_path.name}")
    gguf_path = input_path.resolve()
    if not gguf_path.exists():
        raise click.ClickException(f"File not found: {input_path}")

    reg = registry.load()
    meta = scanner.parse_gguf_header(gguf_path)

    click.echo(f"File: {gguf_path}")
    if meta:
        click.echo(
            f"Detected — Arch: {meta.get('arch','?')}  "
            f"Quant: {meta.get('quant','?')}  "
            f"Params: {meta.get('params','?')}  "
            f"Ctx: {meta.get('ctx','?')}"
        )
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
