import pytest
import aiohttp
import base64
from unittest.mock import AsyncMock, patch, MagicMock
from image_gen import ImageGenClient

@pytest.mark.asyncio
async def test_image_gen_initialization(mock_config):
    client = ImageGenClient(mock_config)
    assert client._api_key == "fake_key"
    await client.close()

@pytest.mark.asyncio
async def test_image_gen_generate_success(mock_config):
    client = ImageGenClient(mock_config)
    
    # Base64 for a tiny transparent pixel
    pixel_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    mock_response_data = {
        "choices": [
            {
                "message": {
                    "images": [
                        {
                            "image_url": {
                                "url": f"data:image/png;base64,{pixel_base64}"
                            }
                        }
                    ]
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
        image_bytes = await client.generate("a happy gork")
        assert image_bytes == base64.b64decode(pixel_base64)
        
    await client.close()

@pytest.mark.asyncio
async def test_image_gen_error_handling(mock_config):
    client = ImageGenClient(mock_config)
    
    mock_resp = MagicMock()
    mock_resp.status = 400
    mock_resp.text = AsyncMock(return_value="Bad Request")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)
    
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.close = AsyncMock()
    mock_session.closed = False
    
    with patch("aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(RuntimeError) as excinfo:
            await client.generate("invalid prompt")
        assert "Image API returned HTTP 400" in str(excinfo.value)
        
    await client.close()
