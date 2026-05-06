import pytest
import aiohttp
from unittest.mock import AsyncMock, patch, MagicMock
from ai import AIClient

@pytest.mark.asyncio
async def test_ai_client_initialization(mock_config):
    client = AIClient(mock_config)
    assert client._model == "openai/gpt-5.2-pro"
    assert client._api_key == "fake_key"
    await client.close()

@pytest.mark.asyncio
async def test_ai_client_chat_success(mock_config):
    client = AIClient(mock_config)
    
    mock_response_data = {
        "choices": [
            {
                "message": {
                    "content": "Hello! I am Gork."
                }
            }
        ]
    }
    
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=mock_response_data)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)
    
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.close = AsyncMock()
    mock_session.closed = False
    
    with patch("aiohttp.ClientSession", return_value=mock_session):
        response = await client.chat("Hi")
        assert response == "Hello! I am Gork."
        
    await client.close()

@pytest.mark.asyncio
async def test_ai_client_generate_response(mock_config):
    client = AIClient(mock_config)
    
    mock_response_data = {
        "choices": [
            {
                "message": {
                    "content": "Gork response"
                }
            }
        ]
    }
    
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=mock_response_data)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)
    
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.close = AsyncMock()
    mock_session.closed = False
    
    with patch("aiohttp.ClientSession", return_value=mock_session):
        response = await client.generate_response("How are you?", author_name="Bob")
        assert response == "Gork response"
        
    await client.close()

@pytest.mark.asyncio
async def test_ai_client_error_handling(mock_config):
    client = AIClient(mock_config)
    
    mock_resp = MagicMock()
    mock_resp.status = 500
    mock_resp.text = AsyncMock(return_value="Internal Server Error")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)
    
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.close = AsyncMock()
    mock_session.closed = False
    
    await client.close()

def test_build_messages_with_parents(mock_config):
    client = AIClient(mock_config)
    guild_parents = {"mother": "Alice", "father": "Bob"}
    messages = client._build_messages("hi", "User", guild_parents=guild_parents)
    
    # Second message should be the parent information
    parent_msg = messages[1]
    assert parent_msg["role"] == "system"
    assert "Alice" in parent_msg["content"]
    assert "Bob" in parent_msg["content"]
    assert "RULES FOR PARENTS" in parent_msg["content"]
