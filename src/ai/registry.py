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
