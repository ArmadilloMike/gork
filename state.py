"""
state.py — Persistent Runtime State
Manages blacklist entries and log channel ID in data/state.json.
Completely separate from config.json (user config vs. runtime data).
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger("gork.state")

STATE_PATH = Path(__file__).parent / "data" / "state.json"

# Shape of the state file
_DEFAULT_STATE: dict[str, Any] = {
    "blacklisted_users": [],     # list[int]  — Discord user IDs
    "blacklisted_channels": [],  # list[int]  — Discord channel IDs
    "whitelisted_channels": [],  # list[int]  — Discord channel IDs
    "auto_respond_channels": [], # list[int]  — Discord channel IDs
    "user_memories": {},         # dict[int, dict[str, str]] — User memories
    "bot_enabled": True,         # bool — Whether Gork responds to messages
    "log_channel_id": None,      # int | None — Discord channel ID
    "last_status_change": None,  # float | None — timestamp of last status change
}


def _load_raw() -> dict[str, Any]:
    """Read state.json from disk, returning defaults if missing or corrupt."""
    if not STATE_PATH.exists():
        return dict(_DEFAULT_STATE)
    try:
        with STATE_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        # Backfill any keys added in later versions
        for key, default in _DEFAULT_STATE.items():
            data.setdefault(key, default)
        return data
    except UnicodeDecodeError:
        log.warning(f"Failed to decode '{STATE_PATH}' as UTF-8. Retrying with 'latin-1'...")
        with STATE_PATH.open("r", encoding="latin-1") as fh:
            data = json.load(fh)
        # Backfill any keys added in later versions
        for key, default in _DEFAULT_STATE.items():
            data.setdefault(key, default)
        return data
    except (json.JSONDecodeError, OSError) as exc:
        log.error(f"Could not read state file ({exc}); using defaults.")
        return dict(_DEFAULT_STATE)


def _save(state: dict[str, Any]) -> None:
    """Write state to disk atomically (write-then-replace)."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
        tmp.replace(STATE_PATH)
    except OSError as exc:
        log.error(f"Failed to save state: {exc}")
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise


# ── Public API ────────────────────────────────────────────────────────────────

class BotState:
    """
    In-memory cache of state.json with save-on-write semantics.
    Instantiate once at startup; pass the instance around.
    """

    def __init__(self) -> None:
        self._data = _load_raw()
        log.info(f"State loaded from '{STATE_PATH}'")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _save(self) -> None:
        _save(self._data)

    # ── Blacklist: users ──────────────────────────────────────────────────────

    def blacklist_user(self, user_id: int) -> bool:
        """
        Add user_id to the blacklist.
        Returns True if added, False if already present.
        """
        if user_id in self._data["blacklisted_users"]:
            return False
        self._data["blacklisted_users"].append(user_id)
        self._save()
        return True

    def unblacklist_user(self, user_id: int) -> bool:
        """
        Remove user_id from the blacklist.
        Returns True if removed, False if not found.
        """
        try:
            self._data["blacklisted_users"].remove(user_id)
        except ValueError:
            return False
        self._save()
        return True

    def is_user_blacklisted(self, user_id: int) -> bool:
        return user_id in self._data["blacklisted_users"]

    @property
    def blacklisted_users(self) -> list[int]:
        return list(self._data["blacklisted_users"])

    # ── Blacklist: channels ───────────────────────────────────────────────────

    def blacklist_channel(self, channel_id: int) -> bool:
        """Add channel_id. Returns True if added, False if already present."""
        if channel_id in self._data["blacklisted_channels"]:
            return False
        self._data["blacklisted_channels"].append(channel_id)
        self._save()
        return True

    def unblacklist_channel(self, channel_id: int) -> bool:
        """Remove channel_id. Returns True if removed, False if not found."""
        try:
            self._data["blacklisted_channels"].remove(channel_id)
        except ValueError:
            return False
        self._save()
        return True

    def is_channel_blacklisted(self, channel_id: int) -> bool:
        return channel_id in self._data["blacklisted_channels"]

    @property
    def blacklisted_channels(self) -> list[int]:
        return list(self._data["blacklisted_channels"])

    # ── Whitelist: channels ───────────────────────────────────────────────────

    def whitelist_channel(self, channel_id: int) -> bool:
        """Add channel_id to whitelist. Returns True if added, False if already present."""
        if channel_id in self._data["whitelisted_channels"]:
            return False
        self._data["whitelisted_channels"].append(channel_id)
        self._save()
        return True

    def unwhitelist_channel(self, channel_id: int) -> bool:
        """Remove channel_id from whitelist. Returns True if removed, False if not found."""
        try:
            self._data["whitelisted_channels"].remove(channel_id)
        except ValueError:
            return False
        self._save()
        return True

    def is_channel_whitelisted(self, channel_id: int) -> bool:
        return channel_id in self._data["whitelisted_channels"]

    @property
    def whitelisted_channels(self) -> list[int]:
        return list(self._data["whitelisted_channels"])

    # ── Auto-respond: channels ────────────────────────────────────────────────

    def add_auto_respond_channel(self, channel_id: int) -> bool:
        """Add channel_id to auto-respond list. Returns True if added, False if already present."""
        if channel_id in self._data["auto_respond_channels"]:
            return False
        self._data["auto_respond_channels"].append(channel_id)
        self._save()
        return True

    def remove_auto_respond_channel(self, channel_id: int) -> bool:
        """Remove channel_id from auto-respond list. Returns True if removed, False if not found."""
        try:
            self._data["auto_respond_channels"].remove(channel_id)
        except ValueError:
            return False
        self._save()
        return True

    def is_auto_respond_channel(self, channel_id: int) -> bool:
        return channel_id in self._data["auto_respond_channels"]

    @property
    def auto_respond_channels(self) -> list[int]:
        return list(self._data["auto_respond_channels"])

    # ── Log channel ───────────────────────────────────────────────────────────

    def set_log_channel(self, channel_id: int) -> None:
        self._data["log_channel_id"] = channel_id
        self._save()

    @property
    def log_channel_id(self) -> int | None:
        return self._data.get("log_channel_id")

    # ── User memories ────────────────────────────────────────────────────────────

    def set_user_memory(self, user_id: int, key: str, value: str) -> None:
        """Set a memory key-value pair for a user."""
        if str(user_id) not in self._data["user_memories"]:
            self._data["user_memories"][str(user_id)] = {}
        self._data["user_memories"][str(user_id)][key] = value
        self._save()

    def get_user_memory(self, user_id: int, key: str) -> str | None:
        """Get a memory value for a user by key."""
        user_mem = self._data["user_memories"].get(str(user_id), {})
        return user_mem.get(key)

    def get_user_memories(self, user_id: int) -> dict[str, str]:
        """Get all memories for a user."""
        return dict(self._data["user_memories"].get(str(user_id), {}))

    def delete_user_memory(self, user_id: int, key: str) -> bool:
        """Delete a memory key for a user. Returns True if deleted."""
        user_mem = self._data["user_memories"].get(str(user_id))
        if user_mem and key in user_mem:
            del user_mem[key]
            if not user_mem:
                del self._data["user_memories"][str(user_id)]
            self._save()
            return True
        return False

    # ── Bot enabled ────────────────────────────────────────────────────────────

    def set_bot_enabled(self, enabled: bool) -> None:
        """Enable or disable the bot globally."""
        self._data["bot_enabled"] = enabled
        self._save()

    @property
    def bot_enabled(self) -> bool:
        return self._data.get("bot_enabled", True)

    # ── Last status change ────────────────────────────────────────────────────────

    def set_last_status_change(self, timestamp: float | None) -> None:
        """Set the timestamp of the last status change."""
        self._data["last_status_change"] = timestamp
        self._save()

    @property
    def last_status_change(self) -> float | None:
        return self._data.get("last_status_change")