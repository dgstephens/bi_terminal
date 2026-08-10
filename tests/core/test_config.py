import json
import stat

import bi_terminal.core.config as config_module


def test_load_missing_file_returns_default_base_url(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path / ".binventory")
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / ".binventory" / "config.json")
    cfg = config_module.load()
    assert cfg == {"base_url": config_module.DEFAULT_URL}


def test_load_corrupt_file_falls_back_to_default(tmp_path, monkeypatch):
    cfg_dir = tmp_path / ".binventory"
    cfg_dir.mkdir()
    cfg_file = cfg_dir / "config.json"
    cfg_file.write_text("{not valid json")
    monkeypatch.setattr(config_module, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_module, "CONFIG_FILE", cfg_file)
    cfg = config_module.load()
    assert cfg == {"base_url": config_module.DEFAULT_URL}


def test_save_then_load_roundtrips(tmp_path, monkeypatch):
    cfg_dir = tmp_path / ".binventory"
    cfg_file = cfg_dir / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_module, "CONFIG_FILE", cfg_file)
    config_module.save({"token": "abc", "userId": "u1"})
    assert json.loads(cfg_file.read_text()) == {"token": "abc", "userId": "u1"}
    assert config_module.load() == {"token": "abc", "userId": "u1"}


def test_save_chmods_file_owner_only(tmp_path, monkeypatch):
    cfg_dir = tmp_path / ".binventory"
    cfg_file = cfg_dir / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_module, "CONFIG_FILE", cfg_file)
    config_module.save({"token": "secret-jwt"})
    mode = stat.S_IMODE(cfg_file.stat().st_mode)
    assert mode == 0o600


def test_clear_auth_persist_false_never_writes_the_file(tmp_path, monkeypatch):
    """Regression test for the door-session fix (2026-08-10) — see
    door_cfg()'s docstring. clear_auth(cfg, persist=False) must still
    remove the in-memory keys (a door session's own logout has to work for
    the rest of that connection) but never touch disk at all."""
    cfg_dir = tmp_path / ".binventory"
    cfg_file = cfg_dir / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_module, "CONFIG_FILE", cfg_file)
    cfg = {"token": "abc", "userId": "u1", "email": "a@b.com"}
    result = config_module.clear_auth(cfg, persist=False)
    assert "token" not in result
    assert not cfg_file.exists()  # never created at all


def test_door_cfg_never_includes_identity(tmp_path, monkeypatch):
    """Real, live-reported bug (2026-08-10): a shared config file meant one
    BBS caller's login leaked to the next caller's connection. door_cfg()
    must never surface token/userId/email even when they're genuinely
    present in the file (e.g. because the same account is ALSO used
    locally with the Textual renderer, which does persist them there)."""
    cfg_dir = tmp_path / ".binventory"
    cfg_file = cfg_dir / "config.json"
    cfg_dir.mkdir()
    cfg_file.write_text(
        json.dumps(
            {
                "token": "leaked-token",
                "userId": "leaked-user",
                "email": "leaked@example.com",
                "base_url": "https://my-backend.example.com/api",
            }
        )
    )
    monkeypatch.setattr(config_module, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_module, "CONFIG_FILE", cfg_file)
    cfg = config_module.door_cfg()
    assert "token" not in cfg
    assert "userId" not in cfg
    assert "email" not in cfg
    # base_url is non-sensitive connection config, not caller identity --
    # deliberately still read from the file (a sysop-configurable setting).
    assert cfg["base_url"] == "https://my-backend.example.com/api"


def test_door_cfg_defaults_base_url_when_no_file_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path / ".binventory")
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / ".binventory" / "config.json")
    cfg = config_module.door_cfg()
    assert cfg["base_url"] == config_module.DEFAULT_URL
    assert "token" not in cfg


def test_clear_auth_removes_only_auth_keys(tmp_path, monkeypatch):
    cfg_dir = tmp_path / ".binventory"
    cfg_file = cfg_dir / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_module, "CONFIG_FILE", cfg_file)
    cfg = {
        "token": "abc",
        "userId": "u1",
        "email": "a@b.com",
        "image_mode": "ansi",
        "base_url": "https://x",
    }
    result = config_module.clear_auth(cfg)
    assert "token" not in result
    assert "userId" not in result
    assert "email" not in result
    assert result["image_mode"] == "ansi"
    assert result["base_url"] == "https://x"
    # persisted too, not just mutated in memory
    assert "token" not in json.loads(cfg_file.read_text())
