"""Migration tests for configs written by older Lazarus versions."""
import json

import pytest

from lazarus.core.config import Config


def write_config(home, data):
    base = home / ".lazarus"
    base.mkdir(parents=True, exist_ok=True)
    (base / "config.json").write_text(json.dumps(data), "utf-8")
    return base / "config.json"


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    return tmp_path


def test_stale_first_run_flag_is_cleared(home):
    """Regression: old configs kept is_first_run=True after setup, which
    redirected the user to a setup page needing credentials they never had."""
    write_config(home, {
        "username": "ali", "password": "mypass123",
        "is_first_run": True,
        "api": {"url": "https://x/v1", "key": "k", "model": "m"},
    })
    cfg = Config()
    assert cfg.data["is_first_run"] is False
    assert cfg.login("ali", "mypass123") is True


def test_genuine_first_run_flag_survives(home):
    """A config still holding a generated username must stay in setup mode."""
    write_config(home, {
        "username": "usr_AbCdEf1234", "password": "generatedpass",
        "is_first_run": True,
        "api": {"url": "", "key": "", "model": "m"},
    })
    cfg = Config()
    assert cfg.data["is_first_run"] is True


def test_api_settings_survive_migration(home):
    write_config(home, {
        "username": "ali", "password": "p",
        "api": {"url": "https://opencode.ai/zen/v1/", "key": "sk-abc",
                "model": "mimo-v2.5-free"},
        "models": [{"name": "m1", "url": "u", "key": "k"}],
        "domain": "example.com",
    })
    cfg = Config()
    assert cfg.data["api"]["url"] == "https://opencode.ai/zen/v1/"
    assert cfg.data["api"]["key"] == "sk-abc"
    assert cfg.data["models"][0]["name"] == "m1"
    assert cfg.data["domain"] == "example.com"


def test_migration_is_persisted_not_just_in_memory(home):
    path = write_config(home, {
        "username": "ali", "password": "mypass123", "is_first_run": True,
        "api": {"url": "", "key": "", "model": "m"},
    })
    Config()
    on_disk = json.loads(path.read_text("utf-8"))
    assert "password" not in on_disk
    assert on_disk["is_first_run"] is False
    assert "secret_key" in on_disk


def test_migration_runs_only_once(home):
    write_config(home, {"username": "ali", "password": "mypass123",
                        "api": {"url": "", "key": "", "model": "m"}})
    first = Config()
    hash_after_first = first.data["password_hash"]
    key_after_first = first.data["secret_key"]

    second = Config()
    assert second.data["password_hash"] == hash_after_first
    assert second.data["secret_key"] == key_after_first
    assert second.login("ali", "mypass123") is True


def test_old_setup_hash_is_dropped(home):
    write_config(home, {
        "username": "ali", "password": "p", "setup_hash": "abc123",
        "api": {"url": "", "key": "", "model": "m"},
    })
    cfg = Config()
    assert "setup_hash" not in cfg.data


def test_missing_api_block_gets_defaults(home):
    write_config(home, {"username": "ali", "password": "p"})
    cfg = Config()
    assert cfg.data["api"]["model"] == "mimo-v2.5-free"
    assert cfg.data["models"] == []
