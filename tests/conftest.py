import pytest
import os
from pathlib import Path

@pytest.fixture
def mock_config():
    return {
        "discord_token": "fake_token",
        "personality": {
            "name": "Gork",
            "description": "A grumpy bot",
            "tone": "Grumpy",
            "temperature": 0.7,
            "style_rules": ["Be short"],
            "behavioral_tendencies": ["Sighs a lot"],
            "response_formatting": "Standard"
        },
        "hackclub_api_key": "fake_key",
        "manager_role_name": "gork-manager"
    }

@pytest.fixture
def temp_state_file(tmp_path):
    state_file = tmp_path / "state.json"
    return str(state_file)
