import pytest
from utils import process_emojis, extract_user_message, split_long_message, image_to_base64
import base64
from io import BytesIO
from PIL import Image

def test_process_emojis():
    assert process_emojis("Hello 😃") == "Hello :grinning_face_with_big_eyes:"
    assert process_emojis("Test") == "Test"

def test_extract_user_message():
    bot_id = 123456
    assert extract_user_message(f"<@{bot_id}> hello", bot_id) == "hello"
    assert extract_user_message(f"<@!{bot_id}>   how are you?", bot_id) == "how are you?"
    assert extract_user_message(f"<@{bot_id}>", bot_id) == "hey"

def test_split_long_message():
    text = "a" * 2500
    chunks = split_long_message(text, max_len=1000)
    assert len(chunks) == 3
    assert len(chunks[0]) == 1000
    assert len(chunks[1]) == 1000
    assert len(chunks[2]) == 500

def test_split_long_message_with_newline():
    text = "line1\n" + "a" * 1995
    chunks = split_long_message(text, max_len=2000)
    assert len(chunks) == 2
    assert chunks[0] == "line1"
    assert chunks[1] == "a" * 1995

@pytest.mark.asyncio
async def test_image_to_base64():
    # Create a small dummy image
    file = BytesIO()
    image = Image.new('RGB', (10, 10))
    image.save(file, 'PNG')
    image_bytes = file.getvalue()
    
    encoded = await image_to_base64(image_bytes)
    assert encoded is not None
    assert isinstance(encoded, str)
    
    # Try invalid bytes
    assert await image_to_base64(b"not an image") is None
