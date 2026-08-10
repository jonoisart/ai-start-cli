"""User settings, kept separate from the model registry so that rebuilding the
registry with `ai scan` cannot destroy preferences."""
import json
import os
from pathlib import Path

import click

from ai import registry

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


def save(data: dict) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(p)
