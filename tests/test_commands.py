import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from discord import app_commands
from commands import _add_reply_context_menu, has_manager_role, manager_role_name

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


@pytest.mark.asyncio
async def test_reply_context_menu_is_user_installed_and_replies_in_target_server():
    import discord

    client = discord.Client(intents=discord.Intents.none())
    tree = app_commands.CommandTree(client)
    state = MagicMock()
    state.bot_enabled = True
    state.is_user_blacklisted.return_value = False
    state.is_channel_blacklisted.return_value = False
    state.has_any_whitelisted_channels.return_value = False
    state.get_user_memories.return_value = {}
    state.get_guild_relationships.return_value = {}
    ai_client = MagicMock()
    ai_client.generate_response = AsyncMock(return_value="Gork: answer")

    command = _add_reply_context_menu(tree, state, ai_client)

    assert isinstance(command, app_commands.ContextMenu)
    assert command.allowed_installs.guild is False
    assert command.allowed_installs.user is True
    assert command.allowed_contexts.guild is True
    assert command.allowed_contexts.dm_channel is False
    assert command.allowed_contexts.private_channel is False

    interaction = MagicMock()
    interaction.guild_id = 123
    interaction.user.id = 456
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    message = MagicMock()
    message.content = "What is this?"
    message.author.display_name = "Example User"
    message.author.id = 789
    message.channel.id = 987

    with patch("commands.extract_images_from_message", new=AsyncMock(return_value=[])):
        await command.callback(interaction, message)

    interaction.response.defer.assert_awaited_once()
    ai_client.generate_response.assert_awaited_once_with(
        user_message="What is this?",
        author_name="Example User",
        context=[{
            "author": "Example User",
            "content": "What is this?",
            "images": [],
        }],
        memories=None,
        images=None,
        guild_relationships=None,
    )
    interaction.followup.send.assert_awaited_once()
    assert interaction.followup.send.await_args.args == ("answer",)
