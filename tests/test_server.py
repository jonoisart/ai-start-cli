import pytest
from unittest.mock import patch, MagicMock
from ai import server


MODEL = {
    "path": "/tmp/model.gguf",
    "ctx": 131072,
    "port": 8083,
    "temp": 0.7,
    "top_p": 0.8,
    "top_k": 20,
    "min_p": 0,
    "n_gpu_layers": 99,
    "flash_attn": True,
    "reasoning": False,
    "jinja": True,
}


@pytest.fixture(autouse=True)
def mock_llama_server():
    with patch("shutil.which", return_value="/opt/homebrew/bin/llama-server"):
        yield


# --- build_argv ---

def test_build_argv_includes_model_path():
    argv = server.build_argv(MODEL)
    assert "-m" in argv
    assert "/tmp/model.gguf" in argv


def test_build_argv_includes_ctx():
    argv = server.build_argv(MODEL)
    assert "-c" in argv
    assert "131072" in argv


def test_build_argv_flash_attn_on():
    argv = server.build_argv(MODEL)
    assert "-fa" in argv
    assert "on" in argv


def test_build_argv_flash_attn_off():
    m = {**MODEL, "flash_attn": False}
    argv = server.build_argv(m)
    assert "-fa" not in argv


def test_build_argv_reasoning_off():
    argv = server.build_argv(MODEL)
    assert "--reasoning-format" in argv
    assert "none" in argv


def test_build_argv_reasoning_on():
    m = {**MODEL, "reasoning": True}
    argv = server.build_argv(m)
    assert "--reasoning-format" not in argv


def test_build_argv_jinja_true():
    argv = server.build_argv(MODEL)
    assert "--jinja" in argv


def test_build_argv_jinja_false():
    m = {**MODEL, "jinja": False}
    argv = server.build_argv(m)
    assert "--jinja" not in argv


# --- find_llama_server ---

def test_find_llama_server_found():
    with patch("shutil.which", return_value="/opt/homebrew/bin/llama-server"):
        assert server.find_llama_server() == "/opt/homebrew/bin/llama-server"


def test_find_llama_server_not_found_raises():
    import click
    with patch("shutil.which", return_value=None):
        with pytest.raises(click.ClickException, match="brew install llama.cpp"):
            server.find_llama_server()


# --- stop ---

def test_stop_kills_process():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="12345\n", returncode=0)
        with patch("os.kill") as mock_kill:
            server.stop(8083)
            mock_kill.assert_called_once_with(12345, 15)  # SIGTERM


def test_stop_no_process_prints_message(capsys):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", returncode=1)
        server.stop(8083)
        captured = capsys.readouterr()
        assert "No server" in captured.out


# --- status ---

def test_status_running():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="12345\n", returncode=0)
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.read.return_value = b'{"status":"ok"}'
            mock_urlopen.return_value = mock_resp
            result = server.status(8083)
            assert result["running"] is True
            assert result["pid"] == 12345


def test_status_not_running():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", returncode=1)
        result = server.status(8083)
        assert result["running"] is False
