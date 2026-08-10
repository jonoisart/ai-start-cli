import pytest


@pytest.fixture(autouse=True)
def isolate_paths(tmp_path, monkeypatch):
    """Redirect config and registry at a temp dir for every test.

    Autouse and mandatory: config.load() *writes* to registry.json during
    migration, so a test that skipped this could rewrite the developer's real
    ~/.config/ai/registry.json. monkeypatch restores the environment on teardown.
    """
    monkeypatch.setenv("AI_REGISTRY_PATH", str(tmp_path / "registry.json"))
    monkeypatch.setenv("AI_CONFIG_PATH", str(tmp_path / "config.json"))
