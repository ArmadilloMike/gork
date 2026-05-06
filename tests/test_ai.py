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

def test_build_messages_with_relationships(mock_config):
    client = AIClient(mock_config)
    guild_relationships = {"mother": "Alice", "father": "Bob", "uncles": ["Charlie", "Dave"]}
    messages = client._build_messages("hi", "User", guild_relationships=guild_relationships)
    
    # Second message should be the relationship information
    rel_msg = messages[1]
    assert rel_msg["role"] == "system"
    assert "Alice" in rel_msg["content"]
    assert "Bob" in rel_msg["content"]
    assert "Charlie" in rel_msg["content"]
    assert "Dave" in rel_msg["content"]
    assert "RULES FOR FAMILY" in rel_msg["content"]
