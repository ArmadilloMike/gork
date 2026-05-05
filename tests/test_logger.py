import pytest
from unittest.mock import MagicMock, AsyncMock
from gork_logger import GorkLogger, LogLevel

@pytest.mark.asyncio
async def test_logger_emit_python(caplog):
    import logging
    # Set level to INFO so info logs are captured
    logging.getLogger("gork.logger").setLevel(logging.INFO)
    
    # Mock bot and state
    bot = MagicMock()
    state = MagicMock()
    state.get_log_channel.return_value = None # Disable Discord emit
    
    logger = GorkLogger(bot, state)
    
    await logger.info("Test Info", detail="some detail")
    
    assert "ℹ️ Test Info" in caplog.text
    assert "detail='some detail'" in caplog.text

@pytest.mark.asyncio
async def test_logger_emit_discord(caplog):
    # Mock bot and state
    bot = MagicMock()
    state = MagicMock()
    state.get_log_channel.return_value = 12345
    
    # Mock channel
    channel = AsyncMock()
    bot.get_channel.return_value = channel
    
    logger = GorkLogger(bot, state)
    
    await logger.success("Success Title", user="Bob")
    
    # Check if channel.send was called with an embed
    assert channel.send.called
    args, kwargs = channel.send.call_args
    embed = kwargs.get("embed")
    assert embed.title == "✅  Success Title"
    assert embed.fields[0].name == "User"
    assert embed.fields[0].value == "Bob"
