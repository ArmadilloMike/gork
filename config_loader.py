"""
config_loader.py — Config & Personality Loader
Reads config.json (or a path from the GORK_CONFIG env var) and returns
a merged dict of bot settings + personality.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger("gork.config")

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "config.json"


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    """
    Load the bot configuration from a JSON file.

    Priority:
      1. Explicit `path` argument
      2. GORK_CONFIG environment variable
      3. config/config.json (default)

    Returns:
        Merged configuration dict.
    """
    config_path = Path(
        path
        or os.environ.get("GORK_CONFIG", DEFAULT_CONFIG_PATH)
    )

    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found at '{config_path}'. "
            "Copy config/config.example.json to config/config.json and fill in your tokens."
        )

    try:
        with config_path.open("r", encoding="utf-8") as fh:
            config: dict[str, Any] = json.load(fh)
    except UnicodeDecodeError:
        log.warning(f"Failed to decode '{config_path}' as UTF-8. Retrying with 'latin-1'...")
        with config_path.open("r", encoding="latin-1") as fh:
            config = json.load(fh)

    log.info(f"Loaded config from '{config_path}'")
    _validate(config)
    # Store the path so we can save back to it if needed
    config["_config_path"] = config_path
    return config


def save_config(config: dict[str, Any]) -> None:
    """Save the configuration back to the file it was loaded from."""
    config_path = config.get("_config_path")
    if not config_path:
        log.error("Cannot save config: no path found in config dict.")
        return

    # Don't save the internal path to the file
    to_save = config.copy()
    to_save.pop("_config_path", None)

    try:
        with open(config_path, "w", encoding="utf-8") as fh:
            json.dump(to_save, fh, indent=2)
        log.info(f"Saved config to '{config_path}'")
    except Exception as e:
        log.error(f"Failed to save config to '{config_path}': {e}")


def _validate(config: dict[str, Any]) -> None:
    """Warn about missing required fields without crashing at load time."""
    required = ["discord_token", "personality"]
    for key in required:
        if not config.get(key):
            log.warning(f"Config is missing or empty field: '{key}'")
