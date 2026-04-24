"""
utils.py — Helper utilities for Gork
Pure functions; no Discord or AI imports.
"""

import re
import logging
import emoji
import base64
import aiohttp
from io import BytesIO
from PIL import Image

log = logging.getLogger("gork.utils")

DISCORD_MAX_CHARS = 2000
SUPPORTED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB


def process_emojis(text: str) -> str:
    """
    Convert emojis to text representations like :thumbs_up:.
    """
    return emoji.demojize(text)


async def download_image(url: str) -> bytes | None:
    """
    Download an image from a URL and return its raw bytes.

    Args:
        url: The URL to download from.

    Returns:
        Raw image bytes, or None if download failed.
    """
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    log.warning(f"Failed to download image: HTTP {resp.status}")
                    return None
                content = await resp.read()
                if len(content) > MAX_IMAGE_SIZE:
                    log.warning(f"Image too large: {len(content)} bytes")
                    return None
                return content
    except Exception as e:
        log.warning(f"Error downloading image: {e}")
        return None


def image_to_base64(image_bytes: bytes) -> str | None:
    """
    Convert image bytes to base64-encoded string.
    Also validates that it's a valid image.

    Args:
        image_bytes: Raw image bytes.

    Returns:
        Base64-encoded string, or None if invalid image.
    """
    try:
        # Validate it's actually an image
        Image.open(BytesIO(image_bytes))
        # Encode to base64
        return base64.b64encode(image_bytes).decode("utf-8")
    except Exception as e:
        log.warning(f"Error processing image: {e}")
        return None


async def extract_images_from_message(message) -> list[dict]:
    """
    Extract all images from a Discord message attachment or embeds.
    Returns a list of dicts with base64 content and detected MIME type.

    Args:
        message: A discord.Message object.

    Returns:
        List of dicts with 'base64' and 'mime_type' keys, or empty list.
    """
    images = []

    # Check message attachments
    if message.attachments:
        for attachment in message.attachments:
            # Check if it's an image
            if attachment.content_type and attachment.content_type.startswith("image/"):
                image_bytes = await download_image(attachment.url)
                if image_bytes:
                    base64_str = image_to_base64(image_bytes)
                    if base64_str:
                        images.append({
                            "base64": base64_str,
                            "mime_type": attachment.content_type,
                        })

    # Check embeds for images
    if message.embeds:
        for embed in message.embeds:
            if embed.image:
                image_bytes = await download_image(embed.image.url)
                if image_bytes:
                    base64_str = image_to_base64(image_bytes)
                    if base64_str:
                        images.append({
                            "base64": base64_str,
                            "mime_type": "image/png",  # Default for embeds
                        })

    return images


def extract_user_message(content: str, bot_user_id: int) -> str:
    """
    Strip all @gork mention(s) from the message and return the cleaned text.

    Discord encodes mentions as <@USER_ID> or <@!USER_ID>.

    Args:
        content:     Raw message content string.
        bot_user_id: The bot's numeric Discord user ID.

    Returns:
        Cleaned message text, or empty string if nothing remains.
    """
    # Remove all forms of the bot mention
    pattern = rf"<@!?{re.escape(str(bot_user_id))}>"
    cleaned = re.sub(pattern, "@gork", content).strip()
    return cleaned


def is_triggered_by_reply(message, bot_user_id: int) -> bool:
    """
    Return True if the message is a reply to a message that mentions @gork.

    Args:
        message:     A discord.Message object.
        bot_user_id: The bot's numeric Discord user ID.

    Returns:
        True when trigger condition 2 is met.
    """
    ref = message.reference
    if ref is None:
        return False

    # The resolved reference is a discord.Message (cached) or PartialMessage
    resolved = ref.resolved
    if resolved is None:
        return False

    # Check if the replied-to message mentions the bot
    mention_pattern = rf"<@!?{re.escape(str(bot_user_id))}>"
    return bool(re.search(mention_pattern, resolved.content or "@gork"))


def split_long_message(text: str, max_len: int = DISCORD_MAX_CHARS) -> list[str]:
    """
    Split a string into chunks that fit within Discord's character limit.
    Tries to split on newlines first; falls back to hard-cutting at max_len.

    Args:
        text:    The full response text.
        max_len: Maximum characters per chunk (default: 2000).

    Returns:
        List of string chunks, each ≤ max_len characters.
    """
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break

        # Try to break at the last newline within the window
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len  # No newline found; hard cut

        chunks.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip()

    return chunks