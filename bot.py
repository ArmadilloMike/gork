"""
bot.py — Gork Discord Bot
Entry point: handles Discord events, routing, and trigger detection.
"""

import discord
import logging
from discord.ext import commands

from ai import AIClient
from config_loader import load_config
from utils import extract_user_message, is_triggered_by_reply, split_long_message

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("gork")

# ── Config & AI ──────────────────────────────────────────────────────────────
config = load_config()
ai_client = AIClient(config)

# ── Discord client setup ──────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True          # Required to read message text
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ── Events ────────────────────────────────────────────────────────────────────

@bot.event
async def on_ready() -> None:
    """Fires once the bot has connected and is ready."""
    log.info(f"Gork is online as {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="@gork mentions",
        )
    )


@bot.event
async def on_message(message: discord.Message) -> None:
    """
    Central message handler.

    Trigger conditions (mutually exclusive, both handled):
      1. Message explicitly mentions @gork  →  use content after the mention.
      2. User replies to a message that mentions @gork  →  use the reply content.

    All other messages are silently ignored.
    """
    # Never respond to ourselves or other bots
    if message.author.bot:
        return

    user_text: str | None = None

    # ── Trigger 1: direct @gork mention ──────────────────────────────────────
    if bot.user in message.mentions:
        user_text = extract_user_message(message.content, bot.user.id)
        log.info(f"Direct mention from {message.author} → '{user_text}'")

    # ── Trigger 2: reply to a message that contains @gork ────────────────────
    elif is_triggered_by_reply(message, bot.user.id):
        user_text = message.content.strip()
        log.info(f"Reply-trigger from {message.author} → '{user_text}'")

    # ── No trigger: ignore ───────────────────────────────────────────────────
    if not user_text:
        return

    # ── Generate & send response ─────────────────────────────────────────────
    async with message.channel.typing():
        try:
            response = await ai_client.generate_response(
                user_message=user_text,
                author_name=str(message.author.display_name),
            )
        except Exception as exc:
            log.exception("AI generation failed")
            await message.reply(
                "⚠️ Something went wrong while thinking. Try again in a moment."
            )
            return

    # Split response if it exceeds Discord's 2000-char limit
    chunks = split_long_message(response)
    for i, chunk in enumerate(chunks):
        if i == 0:
            await message.reply(chunk)
        else:
            await message.channel.send(chunk)

    await bot.process_commands(message)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    token: str = config.get("discord_token", "")
    if not token:
        raise ValueError("discord_token is missing from config.json")
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
