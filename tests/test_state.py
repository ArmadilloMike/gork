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

def test_guild_relationships(mock_state_path):
    state = BotState()
    guild_id = 777
    mother_id = 111
    father_id = 222
    uncle_id = 333
    aunt_id = 444
    
    state.set_guild_relationship(guild_id, "mother", mother_id)
    state.set_guild_relationship(guild_id, "father", father_id)
    state.set_guild_relationship(guild_id, "uncle", uncle_id)
    state.set_guild_relationship(guild_id, "aunt", aunt_id)
    
    rels = state.get_guild_relationships(guild_id)
    assert rels["mother"] == mother_id
    assert rels["father"] == father_id
    assert rels["uncles"] == [uncle_id]
    assert rels["aunts"] == [aunt_id]
    
    # Test persistence
    new_state = BotState()
    rels = new_state.get_guild_relationships(guild_id)
    assert rels["mother"] == mother_id
    assert rels["uncles"] == [uncle_id]
    
    # Test multiple uncles
    state.set_guild_relationship(guild_id, "uncle", 334)
    rels = state.get_guild_relationships(guild_id)
    assert 333 in rels["uncles"]
    assert 334 in rels["uncles"]

    # Test clearing
    state.remove_guild_relationship(guild_id, "mother")
    rels = state.get_guild_relationships(guild_id)
    assert "mother" not in rels
    
    # Test removing specific uncle
    state.remove_guild_relationship(guild_id, "uncle", 333)
    rels = state.get_guild_relationships(guild_id)
    assert rels["uncles"] == [334]
    
    # Test clearing all uncles
    state.remove_guild_relationship(guild_id, "uncle")
    rels = state.get_guild_relationships(guild_id)
    assert "uncles" not in rels
