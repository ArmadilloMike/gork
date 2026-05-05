import pytest
import json
from pathlib import Path
from unittest.mock import patch
from state import BotState

@pytest.fixture
def mock_state_path(tmp_path):
    path = tmp_path / "state.json"
    with patch("state.STATE_PATH", path):
        yield path

def test_bot_state_initialization(mock_state_path):
    state = BotState()
    assert state.bot_enabled is True
    assert state.blacklisted_users == []

def test_blacklist_user(mock_state_path):
    state = BotState()
    user_id = 12345
    
    assert state.blacklist_user(user_id) is True
    assert user_id in state.blacklisted_users
    assert state.is_user_blacklisted(user_id) is True
    
    # Try blacklisting again
    assert state.blacklist_user(user_id) is False

def test_unblacklist_user(mock_state_path):
    state = BotState()
    user_id = 12345
    state.blacklist_user(user_id)
    
    assert state.unblacklist_user(user_id) is True
    assert user_id not in state.blacklisted_users
    
    # Try unblacklisting again
    assert state.unblacklist_user(user_id) is False

def test_persistence(mock_state_path):
    state = BotState()
    state.blacklist_user(111)
    
    # Create a new instance, should load from the same (mocked) path
    new_state = BotState()
    assert 111 in new_state.blacklisted_users

def test_user_memory(mock_state_path):
    state = BotState()
    user_id = 999
    state.set_user_memory(user_id, "favorite_color", "green")
    
    assert state.get_user_memory(user_id, "favorite_color") == "green"
    assert state.get_user_memory(user_id, "unknown") is None
    
    memories = state.get_user_memories(user_id)
    assert memories["favorite_color"] == "green"
    
    state.delete_user_memory(user_id, "favorite_color")
    assert state.get_user_memory(user_id, "favorite_color") is None

def test_bot_enabled_toggle(mock_state_path):
    state = BotState()
    assert state.bot_enabled is True
    state.set_bot_enabled(False)
    assert state.bot_enabled is False
