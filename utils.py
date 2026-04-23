"""
utils.py — Helper utilities for Gork
Pure functions; no Discord or AI imports.
"""

import re
import logging

log = logging.getLogger("gork.utils")

DISCORD_MAX_CHARS = 2000


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
    return bool(re.search(mention_pattern, resolved.content or ""))


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
