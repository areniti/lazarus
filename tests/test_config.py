"""Config tests: hashing, migration, secret key, no plaintext on disk."""
import json

import pytest

from lazarus.core.config import Config


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    return Config()


def test_first_run_generates_credentials(cfg):
    assert cfg.data["is_first_run"] is True
    assert cfg.data["username"].startswith("usr_")
    assert len(cfg.generated_password) == 20
    assert "password" not in cfg.data


def test_password_never_stored_in_plaintext(cfg, tmp_path):
    plain = cfg.generated_password
    cfg.save()
    raw = (tmp_path / ".lazarus" / "config.json").read_text("utf-8")
    assert plain not in raw
    assert "password_hash" in json.loads(raw)


def test_login_accepts_generated_credentials(cfg):
    assert cfg.login(cfg.data["username"], cfg.generated_password) is True


def test_login_rejects_wrong_password(cfg):
    assert cfg.login(cfg.data["username"], "wrong-password") is False


def test_login_rejects_wrong_username(cfg):
    assert cfg.login("nobody", cfg.generated_password) is False


def test_login_rejects_empty(cfg):
    assert cfg.login("", "") is False


def test_hash_is_salted(cfg):
    a = Config.hash_password("same-password")
    b = Config.hash_password("same-password")
    assert a != b


def test_set_password_then_verify(cfg):
    cfg.set_password("brand-new-pass")
    assert cfg.verify_password("brand-new-pass") is True
    assert cfg.verify_password(cfg.generated_password) is False


def test_complete_setup(cfg):
    cfg.complete_setup("ali", "supersecret")
    assert cfg.data["is_first_run"] is False
    assert cfg.login("ali", "supersecret") is True


def test_secret_key_is_unique_per_install(tmp_path, monkeypatch):
    keys = set()
    for name in ("a", "b"):
        home = tmp_path / name
        home.mkdir()
        monkeypatch.setattr("pathlib.Path.home", lambda h=home: h)
        keys.add(Config().data["secret_key"])
    assert len(keys) == 2


def test_migration_from_plaintext_config(tmp_path, monkeypatch):
    base = tmp_path / ".lazarus"
    base.mkdir(parents=True)
    (base / "config.json").write_text(json.dumps({
        "username": "old", "password": "oldpass123",
        "setup_hash": "deadbeef",
        "api": {"url": "", "key": "", "model": "m"},
    }), "utf-8")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    cfg = Config()
    assert "password" not in cfg.data
    assert "setup_hash" not in cfg.data
    assert cfg.login("old", "oldpass123") is True

    on_disk = json.loads((base / "config.json").read_text("utf-8"))
    assert "password" not in on_disk
    assert "oldpass123" not in json.dumps(on_disk)


def test_public_data_hides_secrets(cfg):
    public = cfg.public_data()
    assert "password_hash" not in public
    assert "secret_key" not in public
    assert public["username"] == cfg.data["username"]


def test_corrupt_config_is_backed_up(tmp_path, monkeypatch):
    base = tmp_path / ".lazarus"
    base.mkdir(parents=True)
    (base / "config.json").write_text("{not json", "utf-8")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    cfg = Config()
    assert cfg.data["is_first_run"] is True
    assert (base / "config.json.broken").exists()


def test_add_and_remove_model(cfg):
    cfg.add_model("m1", "http://u", "k")
    assert len(cfg.data["models"]) == 1
    cfg.remove_model(0)
    assert cfg.data["models"] == []
    cfg.remove_model(99)  # out of range must not raise
