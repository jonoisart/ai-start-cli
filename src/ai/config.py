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
