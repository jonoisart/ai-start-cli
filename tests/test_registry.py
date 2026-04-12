import json
import os
import pytest
import click
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


def test_load_corrupt_raises(reg_path):
    reg_path.write_text("{not valid json")
    with pytest.raises(click.ClickException):
        registry.load()


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
