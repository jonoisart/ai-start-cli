"""Registry tests.

`banana` is a deliberately nonsense model nickname. Wherever you see it, the
value is arbitrary throwaway fixture data — the registry code has no idea what
models exist and never references a real name.
"""
import json

import click
import pytest

from ai import registry


@pytest.fixture
def reg_path(tmp_path):
    """The path conftest.isolate_paths pointed AI_REGISTRY_PATH at."""
    return tmp_path / "registry.json"


def test_load_creates_default_when_missing(reg_path):
    data = registry.load()
    assert data == {"models": {}}


def test_load_reads_existing(reg_path):
    reg_path.write_text(json.dumps({"models": {"banana": {"path": "/tmp/banana.gguf"}}}))
    data = registry.load()
    assert data["models"]["banana"]["path"] == "/tmp/banana.gguf"


def test_load_corrupt_raises(reg_path):
    reg_path.write_text("{not valid json")
    with pytest.raises(click.ClickException):
        registry.load()


def test_get_model_found(reg_path):
    reg_path.write_text(json.dumps({
        "models": {"banana": {"path": "/tmp/banana.gguf", "ctx": 4096}}
    }))
    data = registry.load()
    m = registry.get_model(data, "banana")
    assert m["path"] == "/tmp/banana.gguf"


def test_get_model_not_found_raises(reg_path):
    data = registry.load()
    with pytest.raises(click.ClickException):
        registry.get_model(data, "does-not-exist")


def test_add_and_remove_model(reg_path):
    data = registry.load()
    record = {"path": "/tmp/banana.gguf", "ctx": 4096}
    registry.add_model(data, "banana", record)
    registry.save(data)

    data2 = registry.load()
    assert "banana" in data2["models"]

    registry.remove_model(data2, "banana")
    registry.save(data2)

    data3 = registry.load()
    assert "banana" not in data3["models"]


def test_remove_unknown_raises(reg_path):
    data = registry.load()
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
    registry.add_model(data, "banana", {"path": "/tmp/banana.gguf", "ctx": 8192})
    registry.save(data)
    assert reg_path.exists()
    # No .tmp leftover. Path("registry.json").with_suffix(".tmp") is
    # "registry.tmp", not "registry.json.tmp".
    assert not (tmp_path / "registry.tmp").exists()
