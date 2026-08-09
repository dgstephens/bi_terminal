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
