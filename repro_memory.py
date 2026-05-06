import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from ai import AIClient

async def main():
    config = {
        "personality": {
            "name": "Gork",
            "description": "A lazy bot",
            "tone": "Sarcastic",
            "style_rules": ["Use lowercase"],
            "behavioral_tendencies": ["Be lazy"]
        },
        "hackclub_api_key": "fake_key"
    }
    
    client = AIClient(config)
    
    # Context as list of dicts, as passed in bot.py
    context = [
        {"author": "User1", "content": "Hello", "images": []},
        {"author": "Gork", "content": "Whatever", "images": []}
    ]
    
    user_message = "Want me to teach you spanish? My mothertaught me spanish and as your mother, i should teach you."
    author_name = "User1"
    
    print("Testing extract_memories with list of dicts context...")
    
    mock_response_data = {
        "choices": [
            {
                "message": {
                    "content": '{"knows_spanish": "Yes, their mother taught them Spanish.", "role_as_mother": "Claims to be Gork\'s mother."}'
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
        try:
            memories = await client.extract_memories(user_message, author_name, context=context)
            print(f"Extracted: {memories}")
            if "knows_spanish" in memories:
                print("SUCCESS: Memory extracted correctly!")
            else:
                print("FAILURE: Memory not extracted.")
        except Exception as e:
            print(f"Caught unexpected exception: {type(e).__name__}: {e}")
        finally:
            await client.close()

if __name__ == "__main__":
    asyncio.run(main())
