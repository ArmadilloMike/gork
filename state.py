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
    "blacklisted_users": {},     # dict[str, list[int]] — Guild ID -> list of user IDs
    "blacklisted_channels": {},  # dict[str, list[int]] — Guild ID -> list of channel IDs
    "whitelisted_channels": {},  # dict[str, list[int]] — Guild ID -> list of channel IDs
    "auto_respond_channels": {}, # dict[str, list[int]] — Guild ID -> list of channel IDs
    "user_memories": {},         # dict[int, dict[str, str]] — User memories
    "bot_enabled": True,         # bool — Whether Gork responds to messages
    "log_channels": {},          # dict[str, int] — Guild ID -> log channel ID
    "last_status_change": None,  # float | None — timestamp of last status change
    "guild_relationships": {},   # dict[str, dict[str, int|list[int]]] — Guild ID -> {"mother": id, "father": id, "uncles": [ids], "aunts": [ids]}
}


def _load_raw() -> dict[str, Any]:
    """Read state.json from disk, returning defaults if missing or corrupt."""
    if not STATE_PATH.exists():
        return dict(_DEFAULT_STATE)
    try:
        with STATE_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)

        # Migration: blacklisted_users, blacklisted_channels, whitelisted_channels from list to dict
        for key in ["blacklisted_users", "blacklisted_channels", "whitelisted_channels"]:
            if isinstance(data.get(key), list):
                data[key] = {"global": data[key]}

        # Migration: auto_respond_channels from list to dict
        if isinstance(data.get("auto_respond_channels"), list):
            data["auto_respond_channels"] = {"legacy": data["auto_respond_channels"]}

        # Migration: log_channel_id (single) to log_channels (dict)
        if "log_channel_id" in data:
            if data["log_channel_id"] is not None and "log_channels" not in data:
                data["log_channels"] = {"legacy": data["log_channel_id"]}
            del data["log_channel_id"]

        # Migration: guild_parents to guild_relationships
        if "guild_parents" in data:
            data["guild_relationships"] = data.pop("guild_parents")

        # Backfill any keys added in later versions
        for key, default in _DEFAULT_STATE.items():
            data.setdefault(key, default)
        return data
    except UnicodeDecodeError:
        log.warning(f"Failed to decode '{STATE_PATH}' as UTF-8. Retrying with 'latin-1'...")
        with STATE_PATH.open("r", encoding="latin-1") as fh:
            data = json.load(fh)

        # Migration: blacklisted_users, blacklisted_channels, whitelisted_channels from list to dict
        for key in ["blacklisted_users", "blacklisted_channels", "whitelisted_channels"]:
            if isinstance(data.get(key), list):
                data[key] = {"global": data[key]}

        # Migration: auto_respond_channels from list to dict
        if isinstance(data.get("auto_respond_channels"), list):
            data["auto_respond_channels"] = {"legacy": data["auto_respond_channels"]}

        # Migration: log_channel_id (single) to log_channels (dict)
        if "log_channel_id" in data:
            if data["log_channel_id"] is not None and "log_channels" not in data:
                data["log_channels"] = {"legacy": data["log_channel_id"]}
            del data["log_channel_id"]

        # Migration: guild_parents to guild_relationships
        if "guild_parents" in data:
            data["guild_relationships"] = data.pop("guild_parents")

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

    def blacklist_user(self, guild_id: int | None, user_id: int) -> bool:
        """
        Add user_id to the blacklist for a guild.
        Returns True if added, False if already present.
        """
        gid = str(guild_id) if guild_id else "global"
        if gid not in self._data["blacklisted_users"]:
            self._data["blacklisted_users"][gid] = []

        if user_id in self._data["blacklisted_users"][gid]:
            return False
        self._data["blacklisted_users"][gid].append(user_id)
        self._save()
        return True

    def unblacklist_user(self, guild_id: int | None, user_id: int) -> bool:
        """
        Remove user_id from the blacklist for a guild.
        Returns True if removed, False if not found.
        """
        gid = str(guild_id) if guild_id else "global"
        if gid not in self._data["blacklisted_users"]:
            return False
        try:
            self._data["blacklisted_users"][gid].remove(user_id)
            if not self._data["blacklisted_users"][gid]:
                del self._data["blacklisted_users"][gid]
        except ValueError:
            return False
        self._save()
        return True

    def is_user_blacklisted(self, user_id: int, guild_id: int | None = None) -> bool:
        # Check global blacklist first
        if user_id in self._data["blacklisted_users"].get("global", []):
            return True
        # Then check guild-specific blacklist
        if guild_id:
            return user_id in self._data["blacklisted_users"].get(str(guild_id), [])
        return False

    def blacklisted_users(self, guild_id: int | None = None) -> list[int]:
        if guild_id:
            return list(self._data["blacklisted_users"].get(str(guild_id), []))
        return list(self._data["blacklisted_users"].get("global", []))

    # ── Blacklist: channels ───────────────────────────────────────────────────

    def blacklist_channel(self, guild_id: int | None, channel_id: int) -> bool:
        """Add channel_id. Returns True if added, False if already present."""
        gid = str(guild_id) if guild_id else "global"
        if gid not in self._data["blacklisted_channels"]:
            self._data["blacklisted_channels"][gid] = []

        if channel_id in self._data["blacklisted_channels"][gid]:
            return False
        self._data["blacklisted_channels"][gid].append(channel_id)
        self._save()
        return True

    def unblacklist_channel(self, guild_id: int | None, channel_id: int) -> bool:
        """Remove channel_id. Returns True if removed, False if not found."""
        gid = str(guild_id) if guild_id else "global"
        if gid not in self._data["blacklisted_channels"]:
            return False
        try:
            self._data["blacklisted_channels"][gid].remove(channel_id)
            if not self._data["blacklisted_channels"][gid]:
                del self._data["blacklisted_channels"][gid]
        except ValueError:
            return False
        self._save()
        return True

    def is_channel_blacklisted(self, channel_id: int, guild_id: int | None = None) -> bool:
        # Check global blacklist first
        if channel_id in self._data["blacklisted_channels"].get("global", []):
            return True
        # Then check guild-specific blacklist
        if guild_id:
            return channel_id in self._data["blacklisted_channels"].get(str(guild_id), [])
        return False

    def blacklisted_channels(self, guild_id: int | None = None) -> list[int]:
        if guild_id:
            return list(self._data["blacklisted_channels"].get(str(guild_id), []))
        return list(self._data["blacklisted_channels"].get("global", []))

    # ── Whitelist: channels ───────────────────────────────────────────────────

    def whitelist_channel(self, guild_id: int | None, channel_id: int) -> bool:
        """Add channel_id to whitelist. Returns True if added, False if already present."""
        gid = str(guild_id) if guild_id else "global"
        if gid not in self._data["whitelisted_channels"]:
            self._data["whitelisted_channels"][gid] = []

        if channel_id in self._data["whitelisted_channels"][gid]:
            return False
        self._data["whitelisted_channels"][gid].append(channel_id)
        self._save()
        return True

    def unwhitelist_channel(self, guild_id: int | None, channel_id: int) -> bool:
        """Remove channel_id from whitelist. Returns True if removed, False if not found."""
        gid = str(guild_id) if guild_id else "global"
        if gid not in self._data["whitelisted_channels"]:
            return False
        try:
            self._data["whitelisted_channels"][gid].remove(channel_id)
            if not self._data["whitelisted_channels"][gid]:
                del self._data["whitelisted_channels"][gid]
        except ValueError:
            return False
        self._save()
        return True

    def is_channel_whitelisted(self, channel_id: int, guild_id: int | None = None) -> bool:
        # Check global whitelist first
        if channel_id in self._data["whitelisted_channels"].get("global", []):
            return True
        # Then check guild-specific whitelist
        if guild_id:
            return channel_id in self._data["whitelisted_channels"].get(str(guild_id), [])
        return False

    def whitelisted_channels(self, guild_id: int | None = None) -> list[int]:
        if guild_id:
            return list(self._data["whitelisted_channels"].get(str(guild_id), []))
        return list(self._data["whitelisted_channels"].get("global", []))

    def has_any_whitelisted_channels(self, guild_id: int | None = None) -> bool:
        """Returns True if there are any whitelisted channels (global or for guild)."""
        if self._data["whitelisted_channels"].get("global"):
            return True
        if guild_id and self._data["whitelisted_channels"].get(str(guild_id)):
            return True
        return False

    # ── Auto-respond: channels ────────────────────────────────────────────────

    def add_auto_respond_channel(self, guild_id: int, channel_id: int) -> bool:
        """Add channel_id to auto-respond list for a guild. Returns True if added."""
        gid = str(guild_id)
        if gid not in self._data["auto_respond_channels"]:
            self._data["auto_respond_channels"][gid] = []

        if channel_id in self._data["auto_respond_channels"][gid]:
            return False

        self._data["auto_respond_channels"][gid].append(channel_id)
        self._save()
        return True

    def remove_auto_respond_channel(self, guild_id: int, channel_id: int) -> bool:
        """Remove channel_id from auto-respond list for a guild."""
        gid = str(guild_id)
        if gid not in self._data["auto_respond_channels"]:
            return False
        try:
            self._data["auto_respond_channels"][gid].remove(channel_id)
            if not self._data["auto_respond_channels"][gid]:
                del self._data["auto_respond_channels"][gid]
        except ValueError:
            return False
        self._save()
        return True

    def is_auto_respond_channel(self, channel_id: int, guild_id: int | None = None) -> bool:
        """Check if a channel is in auto-respond mode."""
        # Check specific guild
        if guild_id:
            gid = str(guild_id)
            if channel_id in self._data["auto_respond_channels"].get(gid, []):
                return True

        # Check legacy
        if channel_id in self._data["auto_respond_channels"].get("legacy", []):
            return True

        # Fallback: check all guilds if guild_id not provided
        if guild_id is None:
            for channels in self._data["auto_respond_channels"].values():
                if channel_id in channels:
                    return True
        return False

    def get_auto_respond_channels(self, guild_id: int | None = None) -> list[int]:
        """Get all auto-respond channels for a guild (or all if None)."""
        if guild_id:
            return list(self._data["auto_respond_channels"].get(str(guild_id), []))

        # Return flattened list of all channels
        all_channels = []
        for channels in self._data["auto_respond_channels"].values():
            all_channels.extend(channels)
        return list(set(all_channels))

    # ── Log channel ───────────────────────────────────────────────────────────

    def set_log_channel(self, guild_id: int, channel_id: int) -> None:
        """Set the log channel for a specific guild."""
        self._data["log_channels"][str(guild_id)] = channel_id
        self._save()

    def get_log_channel(self, guild_id: int | None) -> int | None:
        """Get the log channel for a guild, falling back to legacy if necessary."""
        if guild_id:
            cid = self._data["log_channels"].get(str(guild_id))
            if cid:
                return cid

        return self._data["log_channels"].get("legacy")

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

    # ── Guild Relationships ──────────────────────────────────────────────────────

    def set_guild_relationship(self, guild_id: int, rel_type: str, user_id: int | None) -> None:
        """Set or clear a relationship for a specific guild."""
        gid = str(guild_id)
        if gid not in self._data["guild_relationships"]:
            self._data["guild_relationships"][gid] = {}
        
        rel_data = self._data["guild_relationships"][gid]
        
        if rel_type in ("mother", "father"):
            if user_id is None:
                if rel_type in rel_data:
                    del rel_data[rel_type]
            else:
                rel_data[rel_type] = user_id
        elif rel_type in ("uncle", "aunt"):
            plural_type = f"{rel_type}s"
            if plural_type not in rel_data:
                rel_data[plural_type] = []
            
            if user_id is not None:
                if user_id not in rel_data[plural_type]:
                    rel_data[plural_type].append(user_id)
        
        # Clean up empty guild entry
        if not self._data["guild_relationships"][gid]:
            del self._data["guild_relationships"][gid]
            
        self._save()

    def remove_guild_relationship(self, guild_id: int, rel_type: str, user_id: int | None = None) -> None:
        """Remove a specific user or all users from a relationship type."""
        gid = str(guild_id)
        if gid not in self._data["guild_relationships"]:
            return

        rel_data = self._data["guild_relationships"][gid]
        
        if rel_type in ("mother", "father"):
            if rel_type in rel_data:
                del rel_data[rel_type]
        elif rel_type in ("uncle", "aunt"):
            plural_type = f"{rel_type}s"
            if plural_type in rel_data:
                if user_id is None:
                    del rel_data[plural_type]
                else:
                    try:
                        rel_data[plural_type].remove(user_id)
                        if not rel_data[plural_type]:
                            del rel_data[plural_type]
                    except ValueError:
                        pass
        
        # Clean up empty guild entry
        if not self._data["guild_relationships"][gid]:
            del self._data["guild_relationships"][gid]

        self._save()

    def get_guild_relationships(self, guild_id: int) -> dict[str, Any]:
        """Get all relationships for a guild."""
        return dict(self._data["guild_relationships"].get(str(guild_id), {}))