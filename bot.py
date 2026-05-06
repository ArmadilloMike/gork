"""
bot.py — Gork Discord Bot
Entry point: Discord events, blacklist enforcement, and slash command sync.
"""

import datetime
import logging
import time
import asyncio
import io

import discord
from discord.ext import commands

from ai import AIClient
from image_gen import ImageGenClient
from commands import register_commands
from config_loader import load_config
from gork_logger import GorkLogger
from state import BotState
from utils import extract_user_message, is_triggered_by_reply, split_long_message, process_emojis, extract_images_from_message

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
    image_client = ImageGenClient(config)
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


# ── Status change ───────────────────────────────────────────────────────────────

async def generate_status(ai_client: AIClient, config: dict) -> str:
    """Generate a new status message using AI."""
    bot_name = config.get("personality", {}).get("name", "Gork")
    prompt = f"Generate a short, funny status message for a Discord bot named {bot_name}. Keep it under 50 characters. Be sarcastic, lazy, and in character."
    try:
        response = await ai_client.chat(prompt, system=f"You are {bot_name}, a lazy sarcastic bot generating status messages.")
        return response.strip()[:50]  # Limit to 50 chars
    except Exception as e:
        log.error(f"Failed to generate status: {e}")
        return "being lazy"


async def generate_image_caption(ai_client: AIClient, config: dict, prompt: str) -> str:
    """Generate a short sentence about the generated image."""
    bot_name = config.get("personality", {}).get("name", "Gork")
    system_prompt = (
        f"You are {bot_name}, a lazy, sarcastic, and super funny bot. "
        "The user just asked you to generate an image, and you did. "
        "Write a VERY short (one short sentence), sarcastic, or funny comment about the image you just 'made' for them. "
        "Keep it in character. No emojis. Lowercase is fine."
    )
    user_prompt = f"The image prompt was: \"{prompt}\". Say something about it."
    
    try:
        response = await ai_client.chat(user_prompt, system=system_prompt)
        return response.strip()
    except Exception as e:
        log.error(f"Failed to generate image caption: {e}")
        return f"here's your {prompt} or whatever."


async def change_status(bot: commands.Bot, state: BotState, ai_client: AIClient, config: dict, custom_status: str | None = None) -> str:
    """Change the bot's status and update the last change time. Returns the new status."""
    if custom_status:
        new_status = custom_status
    else:
        new_status = await generate_status(ai_client, config)

    # Determine activity type
    st_type = config.get("status_type", "listening").lower()
    activity = None

    if st_type == "playing":
        activity = discord.Game(name=new_status)
    elif st_type == "watching":
        activity = discord.Activity(type=discord.ActivityType.watching, name=new_status)
    elif st_type == "competing":
        activity = discord.Activity(type=discord.ActivityType.competing, name=new_status)
    elif st_type == "custom":
        # Note: CustomActivity is often not visible for bots unless set specifically
        # as a custom_status in some libraries, but discord.py supports it.
        activity = discord.CustomActivity(name=new_status)
    else:
        # Default to listening
        activity = discord.Activity(type=discord.ActivityType.listening, name=new_status)

    await bot.change_presence(activity=activity)
    state.set_last_status_change(time.time())
    log.info(f"Status changed to: {new_status} (Type: {st_type})")
    return new_status


async def status_change_loop(bot: commands.Bot, state: BotState, ai_client: AIClient, config: dict) -> None:
    """Loop that changes status every hour."""
    status_interval = config.get("status_change_interval", 3600)
    while True:
        await asyncio.sleep(status_interval)  # default 1 hour
        last_change = state.last_status_change
        if last_change is None or time.time() - last_change >= status_interval:
            await change_status(bot, state, ai_client, config)


# ── Events ────────────────────────────────────────────────────────────────────

_commands_registered = False

@bot.event
async def on_ready() -> None:
    """Fires once connected. Wires logger, registers commands, syncs tree."""
    global gork_log, _commands_registered
    gork_log = GorkLogger(bot, state)

    # on_ready can fire multiple times on reconnect — only register once
    if not _commands_registered:
        register_commands(bot, state, gork_log, config, ai_client, image_client)
        _commands_registered = True

    # Sync slash commands.
    # If 'sync_guild_id' is set in config, sync to that guild(s) instantly (dev mode).
    # Otherwise, sync globally (up to 1 hour to propagate on first run).
    sync_guild_id = config.get("sync_guild_id")
    if sync_guild_id:
        # Support both a single ID and a list of IDs
        guild_ids = sync_guild_id if isinstance(sync_guild_id, list) else [sync_guild_id]
        
        for g_id in guild_ids:
            try:
                guild_obj = discord.Object(id=int(g_id))
                bot.tree.copy_global_to(guild=guild_obj)
                await bot.tree.sync(guild=guild_obj)
                log.info(f"Slash commands synced to guild {g_id} (dev mode).")
            except Exception as e:
                log.error(f"Failed to sync slash commands to guild {g_id}: {e}")
    else:
        await bot.tree.sync()
        log.info("Slash commands synced globally.")

    log.info(f"Gork is online as {bot.user} (ID: {bot.user.id})")
    
    # Use change_status to set initial status with correct type
    initial_status = config.get("initial_status", "being lazy")
    await change_status(bot, state, ai_client, config, custom_status=initial_status)
    
    # Set initial last status change if not set
    if state.last_status_change is None:
        state.set_last_status_change(time.time())
    await gork_log.info(
        "Gork started",
        guild_id=None, # Global start
        user=str(bot.user),
        guilds=str(len(bot.guilds)),
    )

    # Start the status change loop
    bot.loop.create_task(status_change_loop(bot, state, ai_client, config))


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

    # Ignore messages starting with ## (Gork ignore prefix)
    if message.content.startswith("~~"):
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
                guild_id=message.guild.id if message.guild else None,
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
        user_text = process_emojis(user_text)
        trigger_type = "mention"
        log.info(f"Direct mention from {message.author} -> '{user_text}'")

    elif is_triggered_by_reply(message, bot.user.id):
        user_text = message.content.strip()
        user_text = process_emojis(user_text)
        trigger_type = "reply"
        # Include context of the replied message
        if message.reference and message.reference.message_id:
            try:
                referenced = await message.channel.fetch_message(message.reference.message_id)
                user_text = f"Replying to: {process_emojis(referenced.content)}\n\n{user_text}"
            except Exception as e:
                log.warning(f"Failed to fetch referenced message: {e}")
        log.info(f"Reply-trigger from {message.author} -> '{user_text}'")

    elif message.guild is None and not message.content.startswith("!"):
        user_text = message.content.strip()
        user_text = process_emojis(user_text)
        trigger_type = "dm"
        log.info(f"DM from {message.author} -> '{user_text}'")

    elif state.is_auto_respond_channel(message.channel.id, message.guild.id if message.guild else None):
        user_text = message.content.strip()
        user_text = process_emojis(user_text)
        if not user_text:
            user_text = "hey"
        trigger_type = "auto_respond"
        log.info(f"Auto-respond in {message.channel} from {message.author} -> '{user_text}'")

    # ── Image Intent Detection (Implicit/Explicit) ────────────────────────────
    is_image_request = False
    image_prompt = None
    if image_client:
        # Check either the explicitly triggered text or the whole message content if not triggered
        text_to_analyze = user_text if user_text else message.content
        image_prompt = await ai_client.detect_image_intent(text_to_analyze)

        if image_prompt:
            is_image_request = True
            if not user_text:
                trigger_type = "implicit_image"
                user_text = image_prompt  # For logging purposes

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
        log_title = "image generation requested" if is_image_request else "Message received"
        await gork_log.info(
            log_title,
            guild_id=message.guild.id if message.guild else None,
            user=f"{message.author} ({message.author.id})",
            channel=channel_str,
            trigger=trigger_type,
            message=user_text[:200] + ("..." if len(user_text) > 200 else ""),
            jump_url=jump_url,
        )

    # ── Generate & send response ──────────────────────────────────────────────
    async with message.channel.typing():
        if is_image_request:
            try:
                image_bytes = await image_client.generate(image_prompt)
                file = discord.File(fp=io.BytesIO(image_bytes), filename="gork_image.png")
                
                # Generate a short sentence about the image
                caption = await generate_image_caption(ai_client, config, image_prompt)
                await message.reply(content=caption, file=file)

                if gork_log:
                    await gork_log.success(
                        "Image generated (auto)",
                        guild_id=message.guild.id if message.guild else None,
                        user=f"{message.author} ({message.author.id})",
                        prompt=image_prompt[:200],
                        jump_url=jump_url,
                    )
                return
            except Exception as exc:
                log.exception("Auto image generation failed")
                await message.reply(f"⚠️ Couldn't generate that image: {exc}")
                return

        # Extract images from message
        images = await extract_images_from_message(message)
        if images:
            log.info(f"Extracted {len(images)} image(s) from message for multimodal input")
        
        
        # Fetch recent messages for context
        context_limit = config.get("context_message_limit", 15)
        context = []
        try:
            async for msg in message.channel.history(limit=context_limit, before=message):
                # Extract images from this context message
                msg_images = await extract_images_from_message(msg)
                
                # Add to context as a structured dict
                context.append({
                    "author": msg.author.display_name,
                    "content": process_emojis(msg.content),
                    "images": msg_images
                })
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
                images=images if images else None,
            )
        except Exception as exc:
            log.exception("AI generation failed")
            if gork_log:
                await gork_log.error(
                    "AI generation failed",
                    exc=exc,
                    guild_id=message.guild.id if message.guild else None,
                    user=f"{message.author} ({message.author.id})",
                    channel=channel_str,
                    input=user_text[:200],
                    jump_url=jump_url,
                )
            await message.reply("Something went wrong while thinking. Try again in a moment.")
            return

    chunks = split_long_message(response)
    for i, chunk in enumerate(chunks):
        if i == 0:
            await message.reply(chunk)
        else:
            await message.channel.send(chunk)

    # Update user memories based on interaction
    user_id = message.author.id
    # Increment interaction count
    count = int(state.get_user_memory(user_id, "interaction_count") or "0")
    state.set_user_memory(user_id, "interaction_count", str(count + 1))
    # Set last interaction
    state.set_user_memory(user_id, "last_interaction", datetime.datetime.now().isoformat())

    # ── Background Memory Extraction ──────────────────────────────────────────
    try:
        new_memories = await ai_client.extract_memories(
            user_message=user_text,
            author_name=str(message.author.display_name),
            context=context,
            existing_memories=memories
        )
        for key, value in new_memories.items():
            # Clean up key to be a valid identifier
            clean_key = key.strip().lower().replace(" ", "_")
            state.set_user_memory(user_id, clean_key, str(value).strip())
            log.info(f"Auto-saved memory for {message.author}: {clean_key} -> {value}")
    except Exception as e:
        log.warning(f"Background memory extraction failed: {e}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    token: str = config.get("discord_token", "")
    if not token:
        raise ValueError("discord_token is missing from config.json")
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()