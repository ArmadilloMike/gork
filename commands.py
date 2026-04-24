"""
commands.py — Slash Commands for Gork
Registers /blacklist and /setlogchannel as Discord app commands.
All commands are permission-gated to the 'gork-manager' role.
"""

from __future__ import annotations

import io
import logging
import time
from typing import TYPE_CHECKING

import discord
from discord import app_commands

if TYPE_CHECKING:
    from state import BotState
    from gork_logger import GorkLogger
    from image_gen import ImageGenClient

log = logging.getLogger("gork.commands")

# ── Permission check ──────────────────────────────────────────────────────────

def manager_role_name(config: dict) -> str:
    """Return the configured manager role name (default: 'gork-manager')."""
    return config.get("manager_role_name", "gork-manager")


def has_manager_role(interaction: discord.Interaction, role_name: str) -> bool:
    """Return True if the invoking member has the manager role."""
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(
        r.name.lower() == role_name.lower()
        for r in interaction.user.roles
    )


# ── Command registration ──────────────────────────────────────────────────────

def register_commands(
    bot: discord.Client,
    state: "BotState",
    gork_log: "GorkLogger",
    config: dict,
    image_client: "ImageGenClient | None" = None,
) -> None:
    """
    Register all slash commands onto the bot's command tree.
    Call this before bot.run().
    """
    tree = bot.tree
    role_name = manager_role_name(config)

    # ══ /blacklist ════════════════════════════════════════════════════════════

    blacklist_group = app_commands.Group(
        name="blacklist",
        description="Manage Gork's blacklist (requires gork-manager role).",
    )

    # ── /blacklist add user ───────────────────────────────────────────────────

    add_group = app_commands.Group(
        name="add",
        description="Add a user or channel to the blacklist.",
    )

    @add_group.command(name="user", description="Blacklist a user from interacting with Gork.")
    @app_commands.describe(user="The user to blacklist.")
    async def blacklist_add_user(
        interaction: discord.Interaction, user: discord.Member
    ) -> None:
        if not has_manager_role(interaction, role_name):
            await _deny(interaction, gork_log, "blacklist add user")
            return

        added = state.blacklist_user(user.id)
        if added:
            msg = f"✅ **{user.display_name}** (`{user.id}`) has been blacklisted."
            await interaction.response.send_message(msg, ephemeral=True)
            await gork_log.blacklist(
                "User blacklisted",
                user=f"{user} ({user.id})",
                by=f"{interaction.user} ({interaction.user.id})",
                guild=str(interaction.guild),
            )
        else:
            await interaction.response.send_message(
                f"⚠️ **{user.display_name}** is already blacklisted.", ephemeral=True
            )

    # ── /blacklist add channel ────────────────────────────────────────────────

    @add_group.command(name="channel", description="Blacklist a channel from Gork interactions.")
    @app_commands.describe(channel="The channel to blacklist.")
    async def blacklist_add_channel(
        interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        if not has_manager_role(interaction, role_name):
            await _deny(interaction, gork_log, "blacklist add channel")
            return

        added = state.blacklist_channel(channel.id)
        if added:
            msg = f"✅ {channel.mention} has been blacklisted."
            await interaction.response.send_message(msg, ephemeral=True)
            await gork_log.blacklist(
                "Channel blacklisted",
                channel=f"#{channel.name} ({channel.id})",
                by=f"{interaction.user} ({interaction.user.id})",
                guild=str(interaction.guild),
            )
        else:
            await interaction.response.send_message(
                f"⚠️ {channel.mention} is already blacklisted.", ephemeral=True
            )

    blacklist_group.add_command(add_group)

    # ── /blacklist remove ─────────────────────────────────────────────────────

    remove_group = app_commands.Group(
        name="remove",
        description="Remove a user or channel from the blacklist.",
    )

    @remove_group.command(name="user", description="Remove a user from the blacklist.")
    @app_commands.describe(user="The user to un-blacklist.")
    async def blacklist_remove_user(
        interaction: discord.Interaction, user: discord.Member
    ) -> None:
        if not has_manager_role(interaction, role_name):
            await _deny(interaction, gork_log, "blacklist remove user")
            return

        removed = state.unblacklist_user(user.id)
        if removed:
            msg = f"✅ **{user.display_name}** has been removed from the blacklist."
            await interaction.response.send_message(msg, ephemeral=True)
            await gork_log.blacklist(
                "User un-blacklisted",
                user=f"{user} ({user.id})",
                by=f"{interaction.user} ({interaction.user.id})",
                guild=str(interaction.guild),
            )
        else:
            await interaction.response.send_message(
                f"⚠️ **{user.display_name}** is not on the blacklist.", ephemeral=True
            )

    @remove_group.command(name="channel", description="Remove a channel from the blacklist.")
    @app_commands.describe(channel="The channel to un-blacklist.")
    async def blacklist_remove_channel(
        interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        if not has_manager_role(interaction, role_name):
            await _deny(interaction, gork_log, "blacklist remove channel")
            return

        removed = state.unblacklist_channel(channel.id)
        if removed:
            msg = f"✅ {channel.mention} has been removed from the blacklist."
            await interaction.response.send_message(msg, ephemeral=True)
            await gork_log.blacklist(
                "Channel un-blacklisted",
                channel=f"#{channel.name} ({channel.id})",
                by=f"{interaction.user} ({interaction.user.id})",
                guild=str(interaction.guild),
            )
        else:
            await interaction.response.send_message(
                f"⚠️ {channel.mention} is not on the blacklist.", ephemeral=True
            )

    blacklist_group.add_command(remove_group)

    # ── /blacklist list ───────────────────────────────────────────────────────

    @blacklist_group.command(name="list", description="Show all blacklisted users and channels.")
    async def blacklist_list(interaction: discord.Interaction) -> None:
        if not has_manager_role(interaction, role_name):
            await _deny(interaction, gork_log, "blacklist list")
            return

        users = state.blacklisted_users
        channels = state.blacklisted_channels

        embed = discord.Embed(title="🚫 Gork Blacklist", color=discord.Color.dark_red())

        if users:
            user_lines = [f"<@{uid}> (`{uid}`)" for uid in users]
            embed.add_field(
                name=f"Users ({len(users)})",
                value="\n".join(user_lines)[:1024],
                inline=False,
            )
        else:
            embed.add_field(name="Users", value="*None*", inline=False)

        if channels:
            chan_lines = [f"<#{cid}> (`{cid}`)" for cid in channels]
            embed.add_field(
                name=f"Channels ({len(channels)})",
                value="\n".join(chan_lines)[:1024],
                inline=False,
            )
        else:
            embed.add_field(name="Channels", value="*None*", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    tree.add_command(blacklist_group)

    # ══ /whitelist ════════════════════════════════════════════════════════════

    whitelist_group = app_commands.Group(
        name="whitelist",
        description="Manage Gork's whitelist (requires gork-manager role).",
    )

    # ── /whitelist on channel ───────────────────────────────────────────────────

    @whitelist_group.command(name="on", description="Whitelist a channel for Gork interactions.")
    @app_commands.describe(channel="The channel to whitelist.")
    async def whitelist_on_channel(
        interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        if not has_manager_role(interaction, role_name):
            await _deny(interaction, gork_log, "whitelist on")
            return

        added = state.whitelist_channel(channel.id)
        if added:
            msg = f"✅ {channel.mention} has been whitelisted."
            await interaction.response.send_message(msg, ephemeral=True)
            await gork_log.whitelist(
                "Channel whitelisted",
                channel=f"#{channel.name} ({channel.id})",
                by=f"{interaction.user} ({interaction.user.id})",
                guild=str(interaction.guild),
            )
        else:
            await interaction.response.send_message(
                f"⚠️ {channel.mention} is already whitelisted.", ephemeral=True
            )

    # ── /whitelist off channel ──────────────────────────────────────────────────

    @whitelist_group.command(name="off", description="Remove a channel from the whitelist.")
    @app_commands.describe(channel="The channel to remove from whitelist.")
    async def whitelist_off_channel(
        interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        if not has_manager_role(interaction, role_name):
            await _deny(interaction, gork_log, "whitelist off")
            return

        removed = state.unwhitelist_channel(channel.id)
        if removed:
            msg = f"✅ {channel.mention} has been removed from the whitelist."
            await interaction.response.send_message(msg, ephemeral=True)
            await gork_log.whitelist(
                "Channel un-whitelisted",
                channel=f"#{channel.name} ({channel.id})",
                by=f"{interaction.user} ({interaction.user.id})",
                guild=str(interaction.guild),
            )
        else:
            await interaction.response.send_message(
                f"⚠️ {channel.mention} is not on the whitelist.", ephemeral=True
            )

    # ── /whitelist list ───────────────────────────────────────────────────────

    @whitelist_group.command(name="list", description="Show all whitelisted channels.")
    async def whitelist_list(interaction: discord.Interaction) -> None:
        if not has_manager_role(interaction, role_name):
            await _deny(interaction, gork_log, "whitelist list")
            return

        channels = state.whitelisted_channels

        embed = discord.Embed(title="✅ Gork Whitelist", color=discord.Color.green())

        if channels:
            chan_lines = [f"<#{cid}>" for cid in channels]
            embed.add_field(
                name=f"Channels ({len(channels)})",
                value="\n".join(chan_lines)[:1024],
                inline=False,
            )
        else:
            embed.add_field(name="Channels", value="*None*", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    tree.add_command(whitelist_group)

    # ══ /memory ════════════════════════════════════════════════════════════════

    memory_group = app_commands.Group(
        name="memory",
        description="Manage Gork's memories about users (requires gork-manager role).",
    )

    # ── /memory remember ───────────────────────────────────────────────────────

    @memory_group.command(name="remember", description="Remember something about a user.")
    @app_commands.describe(user="The user to remember something about.")
    @app_commands.describe(key="The memory key (e.g., 'favorite_color').")
    @app_commands.describe(value="The value to remember.")
    async def memory_remember(
        interaction: discord.Interaction, user: discord.Member, key: str, value: str
    ) -> None:
        if not has_manager_role(interaction, role_name):
            await _deny(interaction, gork_log, "memory remember")
            return

        state.set_user_memory(user.id, key, value)
        await interaction.response.send_message(
            f"✅ Remembered `{key}` = `{value}` for **{user.display_name}**.", ephemeral=True
        )
        await gork_log.memory(
            "User memory set",
            user=f"{user} ({user.id})",
            key=key,
            value=value[:200],
            by=f"{interaction.user} ({interaction.user.id})",
            guild=str(interaction.guild),
        )

    # ── /memory recall ─────────────────────────────────────────────────────────

    @memory_group.command(name="recall", description="Recall something about a user.")
    @app_commands.describe(user="The user to recall something about.")
    @app_commands.describe(key="The memory key to recall.")
    async def memory_recall(
        interaction: discord.Interaction, user: discord.Member, key: str
    ) -> None:
        if not has_manager_role(interaction, role_name):
            await _deny(interaction, gork_log, "memory recall")
            return

        value = state.get_user_memory(user.id, key)
        if value is not None:
            await interaction.response.send_message(
                f"**{user.display_name}**'s `{key}`: `{value}`", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"No memory found for `{key}` on **{user.display_name}**.", ephemeral=True
            )

    # ── /memory list ───────────────────────────────────────────────────────────

    @memory_group.command(name="list", description="List all memories for a user.")
    @app_commands.describe(user="The user whose memories to list.")
    async def memory_list(interaction: discord.Interaction, user: discord.Member) -> None:
        if not has_manager_role(interaction, role_name):
            await _deny(interaction, gork_log, "memory list")
            return

        memories = state.get_user_memories(user.id)
        if memories:
            mem_lines = [f"`{k}`: `{v}`" for k, v in memories.items()]
            embed = discord.Embed(
                title=f"🧠 Memories for {user.display_name}",
                description="\n".join(mem_lines),
                color=discord.Color.blue(),
            )
        else:
            embed = discord.Embed(
                title=f"🧠 Memories for {user.display_name}",
                description="*No memories stored.*",
                color=discord.Color.blue(),
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /memory forget ─────────────────────────────────────────────────────────

    @memory_group.command(name="forget", description="Forget a memory about a user.")
    @app_commands.describe(user="The user to forget something about.")
    @app_commands.describe(key="The memory key to forget.")
    async def memory_forget(
        interaction: discord.Interaction, user: discord.Member, key: str
    ) -> None:
        if not has_manager_role(interaction, role_name):
            await _deny(interaction, gork_log, "memory forget")
            return

        deleted = state.delete_user_memory(user.id, key)
        if deleted:
            await interaction.response.send_message(
                f"✅ Forgot `{key}` for **{user.display_name}**.", ephemeral=True
            )
            await gork_log.memory(
                "User memory deleted",
                user=f"{user} ({user.id})",
                key=key,
                by=f"{interaction.user} ({interaction.user.id})",
                guild=str(interaction.guild),
            )
        else:
            await interaction.response.send_message(
                f"No memory `{key}` found for **{user.display_name}**.", ephemeral=True
            )

    tree.add_command(memory_group)

    # ══ /gork ══════════════════════════════════════════════════════════════════

    gork_group = app_commands.Group(
        name="gork",
        description="Control Gork's global behavior (requires gork-manager role).",
    )

    # ── /gork enable ──────────────────────────────────────────────────────────

    @gork_group.command(name="enable", description="Enable Gork to respond to messages.")
    async def gork_enable(interaction: discord.Interaction) -> None:
        if not has_manager_role(interaction, role_name):
            await _deny(interaction, gork_log, "gork enable")
            return

        if state.bot_enabled:
            await interaction.response.send_message("Gork is already enabled.", ephemeral=True)
            return

        state.set_bot_enabled(True)
        await interaction.response.send_message("✅ Gork has been enabled.", ephemeral=True)
        await gork_log.mod(
            "Bot enabled",
            by=f"{interaction.user} ({interaction.user.id})",
            guild=str(interaction.guild),
        )

    # ── /gork disable ─────────────────────────────────────────────────────────

    @gork_group.command(name="disable", description="Disable Gork from responding to messages.")
    async def gork_disable(interaction: discord.Interaction) -> None:
        if not has_manager_role(interaction, role_name):
            await _deny(interaction, gork_log, "gork disable")
            return

        if not state.bot_enabled:
            await interaction.response.send_message("Gork is already disabled.", ephemeral=True)
            return

        state.set_bot_enabled(False)
        await interaction.response.send_message("⏸️ Gork has been disabled.", ephemeral=True)
        await gork_log.mod(
            "Bot disabled",
            by=f"{interaction.user} ({interaction.user.id})",
            guild=str(interaction.guild),
        )

    tree.add_command(gork_group)

    # ══ /gork-help ════════════════════════════════════════════════════════════

    @tree.command(
        name="gork-help",
        description="Show how to use Gork and all available commands.",
    )
    async def gork_help(interaction: discord.Interaction) -> None:
        is_manager = has_manager_role(interaction, role_name)

        embed = discord.Embed(
            title="<:gork:0> Gork — Help",
            description=(
                "Gork is a sarcastic AI bot. Mention him or reply to one of his "
                "messages to get a response.\n\u200b"
            ),
            color=discord.Color.blurple(),
        )

        # ── How to trigger ────────────────────────────────────────────────────
        embed.add_field(
            name="💬  How to talk to Gork",
            value=(
                "**Mention him:**  `@gork your message here`\n"
                "**Reply to him:**  Reply to any message Gork sent\n\n"
                "Gork ignores all other messages — he won't eavesdrop."
            ),
            inline=False,
        )

        # ── Slash commands (everyone) ─────────────────────────────────────────
        embed.add_field(
            name="⚙️  Commands",
            value=(
                "`/gork-help` — Show this menu\n"
                "`/imagine <prompt>` — Generate an AI image\n"
            ),
            inline=False,
        )

        # ── Manager-only commands (only shown to managers) ──────────────────────
        if is_manager:
            embed.add_field(
                name="🔒  Manager Commands  *(you have access)*",
                value=(
                    "`/blacklist add user <user>` — Block a user from interacting with Gork\n"
                    "`/blacklist add channel <channel>` — Block an entire channel\n"
                    "`/blacklist remove user <user>` — Unblock a user\n"
                    "`/blacklist remove channel <channel>` — Unblock a channel\n"
                    "`/blacklist list` — View all blacklisted users and channels\n"
                    "`/whitelist on <channel>` — Whitelist a channel for Gork interactions\n"
                    "`/whitelist off <channel>` — Remove a channel from the whitelist\n"
                    "`/whitelist list` — View all whitelisted channels\n"
                    "`/memory remember <user> <key> <value>` — Remember something about a user\n"
                    "`/memory recall <user> <key>` — Recall a memory about a user\n"
                    "`/memory list <user>` — List all memories for a user\n"
                    "`/memory forget <user> <key>` — Forget a memory about a user\n"
                    "`/gork enable` — Turn Gork on to respond to messages\n"
                    "`/gork disable` — Turn Gork off from responding to messages\n"
                    "`/status set <status>` — Set Gork's status message\n"
                    "`/setlogchannel <channel>` — Set the channel for Gork's structured logs"
                ),
                inline=False,
            )

            # ── Manager status indicator ──────────────────────────────────────
            embed.add_field(
                name="\u200b",
                value="✅  You have the **gork-manager** role.",
                inline=False,
            )
        else:
            # ── Non-manager status indicator ──────────────────────────────────
            embed.add_field(
                name="\u200b",
                value="ℹ️  You don't have the **gork-manager** role. Ask a server admin.",
                inline=False,
            )

        embed.set_footer(text="Gork  •  mention @gork to get started")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ══ /setlogchannel ════════════════════════════════════════════════════════

    @tree.command(
        name="setlogchannel",
        description="Set the channel where Gork sends structured logs.",
    )
    @app_commands.describe(channel="The channel to send logs to.")
    async def set_log_channel(
        interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        if not has_manager_role(interaction, role_name):
            await _deny(interaction, gork_log, "setlogchannel")
            return

        state.set_log_channel(channel.id)
        await interaction.response.send_message(
            f"✅ Log channel set to {channel.mention}.", ephemeral=True
        )
        # First log goes to the new channel
        await gork_log.success(
            "Log channel configured",
            channel=f"#{channel.name} ({channel.id})",
            by=f"{interaction.user} ({interaction.user.id})",
            guild=str(interaction.guild),
        )


    # ══ /imagine ══════════════════════════════════════════════════════════════
    if image_client is not None:
        _add_imagine_command(tree, image_client, gork_log)

    # ══ /status ══════════════════════════════════════════════════════════════════

    status_group = app_commands.Group(
        name="status",
        description="Manage Gork's status (requires gork-manager role).",
    )

    @status_group.command(name="set", description="Set Gork's status and reset the timer.")
    @app_commands.describe(status="The new status message.")
    async def status_set(interaction: discord.Interaction, status: str) -> None:
        if not has_manager_role(interaction, role_name):
            await _deny(interaction, gork_log, "status set")
            return

        # Change status
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=status,
            )
        )
        state.set_last_status_change(time.time())
        await interaction.response.send_message(f"✅ Status set to: {status}", ephemeral=True)
        await gork_log.mod(
            "Status changed",
            status=status,
            by=f"{interaction.user} ({interaction.user.id})",
            guild=str(interaction.guild),
        )

    tree.add_command(status_group)

# ── Shared denial helper ──────────────────────────────────────────────────────

async def _deny(
    interaction: discord.Interaction,
    gork_log: "GorkLogger",
    command: str,
) -> None:
    """Send an ephemeral permission-denied reply and emit a security log."""
    await interaction.response.send_message(
        "🔒 You need the **gork-manager** role to use this command.",
        ephemeral=True,
    )
    await gork_log.security(
        "Unauthorized command attempt",
        command=f"/{command}",
        user=f"{interaction.user} ({interaction.user.id})",
        guild=str(interaction.guild),
    )


# ── Image gen import (here to avoid circular imports at module level) ─────────
# Imported inside register_commands so the ImageGenClient is only instantiated
# when the bot actually starts, not at import time.

def _add_imagine_command(
    tree: app_commands.CommandTree,
    image_client: "ImageGenClient",
    gork_log: "GorkLogger",
) -> None:
    """Register /imagine onto the command tree."""

    @tree.command(
        name="imagine",
        description="Generate an image from a text prompt.",
    )
    @app_commands.describe(prompt="Describe the image you want Gork to generate.")
    async def imagine(interaction: discord.Interaction, prompt: str) -> None:
        # Defer immediately — image gen can take 10–30 seconds
        await interaction.response.defer()

        await gork_log.info(
            "Image generation requested",
            user=f"{interaction.user} ({interaction.user.id})",
            channel=f"#{interaction.channel.name}" if hasattr(interaction.channel, 'name') else "DM",
            prompt=prompt[:200],
            jump_url=f"https://discord.com/channels/{interaction.guild.id if interaction.guild else '@me'}/{interaction.channel.id}",
        )

        try:
            image_bytes = await image_client.generate(prompt)
        except RuntimeError as exc:
            error_msg = await interaction.followup.send(
                f"⚠️ Couldn't generate that image: {exc}"
            )
            jump_url = f"https://discord.com/channels/{interaction.guild.id if interaction.guild else '@me'}/{interaction.channel.id}/{error_msg.id}"
            await gork_log.error(
                "Image generation failed",
                exc=exc,
                user=f"{interaction.user} ({interaction.user.id})",
                prompt=prompt[:200],
                jump_url=jump_url,
            )
            return

        file = discord.File(
            fp=io.BytesIO(image_bytes),
            filename="gork_image.png",
        )
        output_msg = await interaction.followup.send(
            content=f'🎨 **"{prompt}"**',
            file=file,
        )
        jump_url = f"https://discord.com/channels/{interaction.guild.id if interaction.guild else '@me'}/{interaction.channel.id}/{output_msg.id}"
        await gork_log.success(
            "Image generated",
            user=f"{interaction.user} ({interaction.user.id})",
            prompt=prompt[:200],
            jump_url=jump_url,
        )
