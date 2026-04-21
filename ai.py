"""
ai.py — Hack Club AI Proxy Wrapper
Handles all communication with the Hack Club AI API.
Isolated from Discord logic; receives plain strings, returns plain strings.
"""

import asyncio
import logging
from typing import Any

import aiohttp

log = logging.getLogger("gork.ai")

# ── Constants ─────────────────────────────────────────────────────────────────
HACKCLUB_API_URL = "https://ai.hackclub.com/chat/completions"
MODEL = "google/gemini-flash-1.5"          # Hack Club proxy model
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class AIClient:
    """
    Thin async wrapper around the Hack Club AI proxy.

    Responsibilities:
    - Build system + user prompts
    - Send HTTP requests to the proxy
    - Parse and return the text response
    - Handle errors gracefully
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._personality: dict[str, Any] = config.get("personality", {})
        self._api_key: str = config.get("hackclub_api_key", "")
        self._model: str = config.get("model", MODEL)
        self._session: aiohttp.ClientSession | None = None

    # ── Session management ────────────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return (or lazily create) the shared aiohttp session."""
        if self._session is None or self._session.closed:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
        return self._session

    async def close(self) -> None:
        """Cleanly close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    # ── Prompt construction ───────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        """
        Assemble the system prompt from the personality config block.
        Every key in the personality dict is injected here so that
        changing personality.json is all that's needed to restyle the bot.
        """
        p = self._personality
        lines: list[str] = [
            f"You are {p.get('name', 'Gork')}, a Discord bot.",
            "",
            f"## Persona",
            f"{p.get('description', '')}",
            "",
            f"## Tone",
            f"{p.get('tone', '')}",
            "",
            f"## Style Rules",
        ]
        for rule in p.get("style_rules", []):
            lines.append(f"- {rule}")

        lines += [
            "",
            f"## Behavioral Tendencies",
        ]
        for tendency in p.get("behavioral_tendencies", []):
            lines.append(f"- {tendency}")

        lines += [
            "",
            f"## Response Formatting",
            f"{p.get('response_formatting', '')}",
            "",
            "## Important Constraints",
            "- Never fabricate @mentions or pretend to tag users.",
            "- Stay strictly in character at all times.",
            "- If you don't know something, admit it in character.",
        ]

        return "\n".join(lines)

    def _build_messages(
        self, user_message: str, author_name: str
    ) -> list[dict[str, str]]:
        """Return the full messages list for the API call."""
        system_prompt = self._build_system_prompt()
        user_prompt = (
            f"[Responding to Discord user '{author_name}']\n\n{user_message}"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    # ── API call ──────────────────────────────────────────────────────────────

    async def generate_response(
        self, user_message: str, author_name: str = "User"
    ) -> str:
        """
        Send a prompt to the Hack Club AI proxy and return the text reply.

        Args:
            user_message: The cleaned message from the Discord user.
            author_name:  Display name of the Discord user (for context).

        Returns:
            The AI-generated response as a plain string.

        Raises:
            RuntimeError: On non-200 HTTP status or malformed response.
        """
        messages = self._build_messages(user_message, author_name)
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": 1024,
            "temperature": self._personality.get("temperature", 0.85),
        }

        log.debug(f"Sending request to Hack Club AI | model={self._model}")

        session = await self._get_session()
        try:
            async with session.post(
                HACKCLUB_API_URL, json=payload
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(
                        f"Hack Club AI returned HTTP {resp.status}: {body[:300]}"
                    )

                data: dict[str, Any] = await resp.json()
                return self._parse_response(data)

        except aiohttp.ClientError as exc:
            log.error(f"Network error contacting Hack Club AI: {exc}")
            raise RuntimeError(f"Network error: {exc}") from exc

    # ── Response parsing ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> str:
        """
        Extract the assistant's text from the OpenAI-compatible response body.

        Expected shape:
          { "choices": [ { "message": { "content": "..." } } ] }
        """
        try:
            content: str = data["choices"][0]["message"]["content"]
            return content.strip()
        except (KeyError, IndexError, TypeError) as exc:
            log.error(f"Unexpected response shape: {data}")
            raise RuntimeError(f"Could not parse AI response: {exc}") from exc
