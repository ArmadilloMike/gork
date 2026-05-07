import pytest
from unittest.mock import MagicMock
from commands import has_manager_role, manager_role_name

def test_manager_role_name():
    assert manager_role_name({"manager_role_name": "boss"}) == "boss"
    assert manager_role_name({}) == "gork-manager"

def test_has_manager_role():
    import discord
    # Mock role
    role_mock = MagicMock()
    role_mock.name = "gork-manager"
    
    # Mock user with roles, must be spec=discord.Member for isinstance check
    user_mock = MagicMock(spec=discord.Member)
    user_mock.roles = [role_mock]
    user_mock.id = 12345
    
    # Mock interaction
    interaction_mock = MagicMock()
    interaction_mock.user = user_mock
    
    # Config mock
    config = {"manager_role_name": "gork-manager", "gork_owner": 99999}
    
    # Check with correct role
    assert has_manager_role(interaction_mock, config) is True
    
    # Check with incorrect role
    config["manager_role_name"] = "admin"
    assert has_manager_role(interaction_mock, config) is False
    
    # Check with gork_owner (even if role is wrong)
    config["gork_owner"] = 12345
    assert has_manager_role(interaction_mock, config) is True

    # Check with gork_owner as string ID
    config["gork_owner"] = "12345"
    assert has_manager_role(interaction_mock, config) is True
    
    # Check with non-Member user (but still owner)
    interaction_mock.user = MagicMock(spec=discord.User)
    interaction_mock.user.id = 12345
    assert has_manager_role(interaction_mock, config) is True

    # Check with non-Member user (not owner)
    interaction_mock.user.id = 67890
    assert has_manager_role(interaction_mock, config) is False
