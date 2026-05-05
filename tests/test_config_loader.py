import pytest
import json
import os
from pathlib import Path
from config_loader import load_config

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
