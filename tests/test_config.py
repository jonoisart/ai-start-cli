"""Config tests.

`banana` is a deliberately nonsense model nickname. Wherever you see it, the
value is arbitrary throwaway fixture data — the config code has no idea what
models exist and never references a real name.
"""
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


# --- migration off the legacy single-file layout ---

@pytest.fixture
def reg_path(tmp_path):
    """The path conftest.isolate_paths pointed AI_REGISTRY_PATH at."""
    return tmp_path / "registry.json"


def write_legacy_registry(reg_path, defaults):
    """A pre-split registry.json: defaults and models together in one file."""
    reg_path.write_text(json.dumps({
        "defaults": defaults,
        "models": {"banana": {"path": "/tmp/banana.gguf", "ctx": 4096}},
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
    assert on_disk["models"]["banana"]["path"] == "/tmp/banana.gguf"


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
