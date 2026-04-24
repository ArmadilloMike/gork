"""
bot.py — Gork Discord Bot
Entry point: Discord events, blacklist enforcement, and slash command sync.
"""

import datetime
import logging

import discord
from discord.ext import commands

from ai import AIClient
from image_gen import ImageGenClient
from commands import register_commands
from config_loader import load_config
from gork_logger import GorkLogger
from state import BotState
from utils import extract_user_message, is_triggered_by_reply, split_long_message

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("gork")

# ── Config, state, AI ─────────────────────────────────────────────────────────
config    = load_config()
state     = BotState()
ai_client = AIClient(config)

# ImageGenClient uses the same API key — instantiation is safe to do at module
# level; it only creates an aiohttp session lazily on first use.
try:
    image_client = ImageGenClient(
        api_key=config.get("hackclub_api_key", ""),
        image_style=config.get("personality", {}).get("image_style", ""),
    )
except ValueError:
    image_client = None
    log.warning("Image generation disabled: hackclub_api_key not set.")

# ── Discord client ────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# GorkLogger is created after bot exists (needs the client reference)
gork_log: GorkLogger | None = None


# ── Events ────────────────────────────────────────────────────────────────────

_commands_registered = False

@bot.event
async def on_ready() -> None:
    """Fires once connected. Wires logger, registers commands, syncs tree."""
    global gork_log, _commands_registered
    gork_log = GorkLogger(bot, state)

    # on_ready can fire multiple times on reconnect — only register once
    if not _commands_registered:
        register_commands(bot, state, gork_log, config, image_client)
        _commands_registered = True

    # Sync slash commands.
    # If 'sync_guild_id' is set in config, sync to that guild instantly (dev mode).
    # Otherwise, sync globally (up to 1 hour to propagate on first run).
    guild_id: int | None = config.get("sync_guild_id")
    if guild_id:
        guild_obj = discord.Object(id=guild_id)
        bot.tree.copy_global_to(guild=guild_obj)
        await bot.tree.sync(guild=guild_obj)
        log.info(f"Slash commands synced to guild {guild_id} (dev mode).")
    else:
        await bot.tree.sync()
        log.info("Slash commands synced globally.")

    log.info(f"Gork is online as {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="dont be horny",
        )
    )
    await gork_log.info(
        "Gork started",
        user=str(bot.user),
        guilds=str(len(bot.guilds)),
    )


@bot.event
async def on_message(message: discord.Message) -> None:
    """
    Central message handler.

    Trigger conditions:
      1. Message explicitly mentions @gork
      2. User replies to a message that contains @gork

    Blacklist gates:
      - Blacklisted users    -> silently ignored
      - Blacklisted channels -> silently ignored
    """
    # Never respond to bots (including ourselves)
    if message.author.bot:
        return

    # ── Blacklist: channel ────────────────────────────────────────────────────
    if state.is_channel_blacklisted(message.channel.id):
        return

    # ── Whitelist: channel ────────────────────────────────────────────────────
    if state.whitelisted_channels and not state.is_channel_whitelisted(message.channel.id):
        return

    # ── Bot enabled ────────────────────────────────────────────────────────────
    if not state.bot_enabled:
        return

    # ── Blacklist: user ───────────────────────────────────────────────────────
    if state.is_user_blacklisted(message.author.id):
        # Only log when the blacklisted user actually tried to trigger Gork,
        # not on every message they send in the server.
        is_attempt = (
            bot.user in message.mentions
            or is_triggered_by_reply(message, bot.user.id)
        )
        if is_attempt and gork_log:
            await gork_log.mod(
                "Blocked blacklisted user",
                user=f"{message.author} ({message.author.id})",
                channel=f"#{message.channel.name} ({message.channel.id})",
                content=message.content[:200],
                jump_url=f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}",
            )
        return

    # ── Trigger detection ─────────────────────────────────────────────────────
    user_text: str | None = None
    trigger_type: str | None = None

    if bot.user in message.mentions:
        user_text = extract_user_message(message.content, bot.user.id)
        trigger_type = "mention"
        log.info(f"Direct mention from {message.author} -> '{user_text}'")

    elif is_triggered_by_reply(message, bot.user.id):
        user_text = message.content.strip()
        trigger_type = "reply"
        # Include context of the replied message
        if message.reference and message.reference.message_id:
            try:
                referenced = await message.channel.fetch_message(message.reference.message_id)
                user_text = f"Replying to: {referenced.content}\n\n{user_text}"
            except Exception as e:
                log.warning(f"Failed to fetch referenced message: {e}")
        log.info(f"Reply-trigger from {message.author} -> '{user_text}'")

    elif message.guild is None and not message.content.startswith("!"):
        user_text = message.content.strip()
        trigger_type = "dm"
        log.info(f"DM from {message.author} -> '{user_text}'")

    if not user_text:
        await bot.process_commands(message)
        return

    # ── Prepare logging info ───────────────────────────────────────────────────
    if message.guild:
        jump_url = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
        channel_str = f"#{message.channel.name}"
    else:
        jump_url = f"https://discord.com/channels/@me/{message.channel.id}/{message.id}"
        channel_str = "DM"

    # ── Log the interaction ───────────────────────────────────────────────────
    if gork_log:
        await gork_log.info(
            "Message received",
            user=f"{message.author} ({message.author.id})",
            channel=channel_str,
            trigger=trigger_type,
            message=user_text[:200] + ("..." if len(user_text) > 200 else ""),
            jump_url=jump_url,
        )

    # ── Generate & send response ──────────────────────────────────────────────
    thinking_msg = await message.reply("i am thinking now.")
    async with message.channel.typing():
        # Fetch recent messages for context
        context_limit = config.get("context_message_limit", 5)
        context = []
        try:
            async for msg in message.channel.history(limit=context_limit, before=message):
                # Skip bot messages to avoid self-reference loops
                if msg.author.bot:
                    continue
                # Format as "Author: Message"
                context.append(f"{msg.author.display_name}: {msg.content}")
            # Reverse to oldest first
            context.reverse()
        except Exception as e:
            log.warning(f"Failed to fetch message history: {e}")
            context = None

        # Fetch user memories
        memories = state.get_user_memories(message.author.id)
        if not memories:
            memories = None

        try:
            response = await ai_client.generate_response(
                user_message=user_text,
                author_name=str(message.author.display_name),
                context=context,
                memories=memories,
            )
        except Exception as exc:
            log.exception("AI generation failed")
            if gork_log:
                if message.guild:
                    jump_url_error = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{thinking_msg.id}"
                else:
                    jump_url_error = f"https://discord.com/channels/@me/{message.channel.id}/{thinking_msg.id}"
                await gork_log.error(
                    "AI generation failed",
                    exc=exc,
                    user=f"{message.author} ({message.author.id})",
                    channel=channel_str,
                    input=user_text[:200],
                    jump_url=jump_url_error,
                )
            await thinking_msg.edit(content="Something went wrong while thinking. Try again in a moment.")
            return

    chunks = split_long_message(response)
    for i, chunk in enumerate(chunks):
        if i == 0:
            await thinking_msg.edit(content=chunk)
        else:
            await message.channel.send(chunk)

    # Update user memories based on interaction
    user_id = message.author.id
    # Increment interaction count
    count = int(state.get_user_memory(user_id, "interaction_count") or "0")
    state.set_user_memory(user_id, "interaction_count", str(count + 1))
    # Set last interaction
    state.set_user_memory(user_id, "last_interaction", datetime.datetime.now().isoformat())
    # Basic sentiment analysis
    lower_text = user_text.lower()
    if any(word in lower_text for word in ["thank", "thanks", "appreciate", "good job", "well done"]):
        state.set_user_memory(user_id, "attitude", "grateful")
    elif any(word in lower_text for word in ["stupid", "dumb", "idiot", "bad", "hate"]):
        state.set_user_memory(user_id, "attitude", "critical")
    elif any(word in lower_text for word in ["love", "awesome", "great", "amazing"]):
        state.set_user_memory(user_id, "attitude", "positive")

    await bot.process_commands(message)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    token: str = config.get("discord_token", "")
    if not token:
        raise ValueError("discord_token is missing from config.json")
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()