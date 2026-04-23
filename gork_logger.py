"""
gork_logger.py — Dual Logger (console + Discord channel)
Wraps Python's standard logger and optionally mirrors structured
log embeds to a designated Discord channel stored in BotState.
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from state import BotState

log = logging.getLogger("gork.logger")


class LogLevel(Enum):
    INFO      = ("ℹ️",  discord.Color.blurple())
    SUCCESS   = ("✅",  discord.Color.green())
    WARNING   = ("⚠️",  discord.Color.yellow())
    ERROR     = ("❌",  discord.Color.red())
    MOD       = ("🔨",  discord.Color.orange())
    BLACKLIST = ("🚫",  discord.Color.dark_red())
    WHITELIST = ("✅",  discord.Color.dark_green())
    SECURITY  = ("🔒",  discord.Color.dark_gold())


class GorkLogger:
    """
    Structured logger that writes to both the Python logging system
    and a Discord channel embed (when a log channel is configured).

    Usage:
        gork_log = GorkLogger(bot, state)
        await gork_log.info("Bot started", details="Gork#1234")
        await gork_log.blacklist("User blacklisted", target="@someone")
        await gork_log.error("AI failed", exc=some_exception)
    """

    def __init__(self, bot: discord.Client, state: "BotState") -> None:
        self._bot = bot
        self._state = state

    # ── Public log methods ────────────────────────────────────────────────────

    async def info(self, title: str, **fields: str) -> None:
        await self._emit(LogLevel.INFO, title, **fields)

    async def success(self, title: str, **fields: str) -> None:
        await self._emit(LogLevel.SUCCESS, title, **fields)

    async def warning(self, title: str, **fields: str) -> None:
        await self._emit(LogLevel.WARNING, title, **fields)

    async def error(self, title: str, exc: Exception | None = None, **fields: str) -> None:
        if exc is not None:
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            # Truncate so it fits in an embed field (1024 char limit)
            fields["traceback"] = f"```\n{tb[-900:]}\n```"
        await self._emit(LogLevel.ERROR, title, **fields)

    async def mod(self, title: str, **fields: str) -> None:
        """Moderation-related actions (blacklist changes, etc.)"""
        await self._emit(LogLevel.MOD, title, **fields)

    async def blacklist(self, title: str, **fields: str) -> None:
        await self._emit(LogLevel.BLACKLIST, title, **fields)

    async def whitelist(self, title: str, **fields: str) -> None:
        await self._emit(LogLevel.WHITELIST, title, **fields)

    async def memory(self, title: str, **fields: str) -> None:
        await self._emit(LogLevel.MOD, title, **fields)

    async def security(self, title: str, **fields: str) -> None:
        """Permission failures and unauthorized access attempts."""
        await self._emit(LogLevel.SECURITY, title, **fields)

    # ── Core emit ─────────────────────────────────────────────────────────────

    async def _emit(self, level: LogLevel, title: str, **fields: str) -> None:
        """
        Write to Python logger and, if configured, send a Discord embed.
        Never raises — log failures must not crash the bot.
        """
        emoji, _ = level.value

        # ── Python logger ─────────────────────────────────────────────────────
        field_str = "  ".join(f"{k}={v!r}" for k, v in fields.items())
        py_msg = f"{emoji} {title}" + (f" | {field_str}" if field_str else "")

        if level in (LogLevel.ERROR,):
            log.error(py_msg)
        elif level in (LogLevel.WARNING, LogLevel.SECURITY):
            log.warning(py_msg)
        else:
            log.info(py_msg)

        # ── Discord embed ─────────────────────────────────────────────────────
        channel_id = self._state.log_channel_id
        if channel_id is None:
            return

        channel = self._bot.get_channel(channel_id)
        if channel is None:
            log.warning(f"Log channel {channel_id} not found in cache.")
            return

        embed = self._build_embed(level, title, fields)
        jump_url = fields.pop("jump_url", None)
        view = None
        if jump_url:
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="Jump to Message", url=jump_url))
        try:
            await channel.send(embed=embed, view=view)
        except discord.Forbidden:
            log.warning(f"Missing permission to send to log channel {channel_id}.")
        except discord.HTTPException as exc:
            log.warning(f"Failed to send log embed: {exc}")

    # ── Embed builder ─────────────────────────────────────────────────────────

    @staticmethod
    def _build_embed(
        level: LogLevel, title: str, fields: dict[str, str]
    ) -> discord.Embed:
        emoji, color = level.value
        embed = discord.Embed(
            title=f"{emoji}  {title}",
            color=color,
            timestamp=datetime.now(tz=timezone.utc),
        )
        embed.set_footer(text=f"Gork  •  {level.name}")

        for name, value in fields.items():
            # Inline for short values, block for long ones
            inline = len(str(value)) < 60 and not str(value).startswith("```")
            embed.add_field(
                name=name.replace("_", " ").title(),
                value=str(value)[:1024] or "—",
                inline=inline,
            )

        return embed