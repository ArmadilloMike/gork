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
    
    # Mock interaction
    interaction_mock = MagicMock()
    interaction_mock.user = user_mock
    
    # Check with correct role
    assert has_manager_role(interaction_mock, "gork-manager") is True
    assert has_manager_role(interaction_mock, "GORK-MANAGER") is True
    
    # Check with incorrect role
    assert has_manager_role(interaction_mock, "admin") is False
    
    # Check with non-Member user
    interaction_mock.user = MagicMock(spec=discord.User)
    assert has_manager_role(interaction_mock, "gork-manager") is False
