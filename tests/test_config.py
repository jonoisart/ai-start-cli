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
