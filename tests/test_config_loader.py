import pytest
import json
import os
from pathlib import Path
from config_loader import load_config, save_config

def test_load_config_success(tmp_path):
    config_data = {
        "discord_token": "test_token",
        "personality": {"name": "TestBot"}
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data), encoding="utf-8")
    
    loaded = load_config(config_file)
    assert loaded["discord_token"] == "test_token"
    assert loaded["personality"]["name"] == "TestBot"

def test_load_config_not_found():
    with pytest.raises(FileNotFoundError):
        load_config("non_existent_file.json")

def test_load_config_env_var(tmp_path, monkeypatch):
    config_data = {
        "discord_token": "env_token",
        "personality": {"name": "EnvBot"}
    }
    config_file = tmp_path / "env_config.json"
    config_file.write_text(json.dumps(config_data), encoding="utf-8")
    
    monkeypatch.setenv("GORK_CONFIG", str(config_file))
    
    loaded = load_config()
    assert loaded["discord_token"] == "env_token"

def test_validate_missing_fields(tmp_path, caplog):
    # Field 'personality' is missing
    config_data = {
        "discord_token": "some_token"
    }
    config_file = tmp_path / "invalid_config.json"
    config_file.write_text(json.dumps(config_data), encoding="utf-8")
    
    load_config(config_file)
    assert "Config is missing or empty field: 'personality'" in caplog.text

def test_save_config(tmp_path):
    config_data = {
        "discord_token": "test_token",
        "personality": {"name": "TestBot"},
        "sync_guild_id": [123]
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data), encoding="utf-8")
    
    # Load and verify path storage
    loaded = load_config(config_file)
    assert loaded["_config_path"] == config_file
    
    # Modify and save
    loaded["sync_guild_id"].append(456)
    save_config(loaded)
    
    # Verify file content
    with open(config_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    
    assert saved_data["sync_guild_id"] == [123, 456]
    assert "_config_path" not in saved_data
    assert saved_data["discord_token"] == "test_token"
