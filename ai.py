"""
ai.py — Hack Club AI Proxy Wrapper
Handles all communication with the Hack Club AI API.
Isolated from Discord logic; receives plain strings, returns plain strings.
"""

import asyncio
import logging
import json
from typing import Any

import aiohttp

log = logging.getLogger("gork.ai")

# ── Constants ─────────────────────────────────────────────────────────────────
HACKCLUB_API_URL = "https://ai.hackclub.com/proxy/v1/chat/completions"
MODEL = "openai/gpt-5.2-pro"                   # Default Hack Club proxy model
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=180)


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
        self._model: str = config.get("model", MODEL)
        self._api_url: str = config.get("api_url", HACKCLUB_API_URL)
        self._session: aiohttp.ClientSession | None = None

        # API key is required — get one at https://ai.hackclub.com/dashboard
        api_key: str = config.get("hackclub_api_key", "")
        if not api_key:
            raise ValueError(
                "hackclub_api_key is missing from config.json. "
                "Create a key at https://ai.hackclub.com/dashboard"
            )
        self._api_key = api_key

    # ── Session management ────────────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return (or lazily create) the shared aiohttp session."""
        if self._session is None or self._session.closed:
            # Authorization is required for all Hack Club AI requests
            headers: dict[str, str] = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            }
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
        return self._session

    async def close(self) -> None:
        """Cleanly close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    # ── Simple Chat ───────────────────────────────────────────────────────────

    async def chat(self, prompt: str, system: str | None = None) -> str:
        """
        Simple chat completion without personality/context overhead.
        Useful for internal tasks like classification or status generation.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": 1024,
            "temperature": 0.7,
        }

        try:
            session = await self._get_session()
            async with session.post(self._api_url, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"AI API error: {body[:300]}")
                data: dict[str, Any] = await resp.json()
                return self._parse_response(data)
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            log.error(f"Chat request failed: {exc}")
            raise RuntimeError(f"Network error during chat: {exc}") from exc

    # ── Image Intent Detection ────────────────────────────────────────────────

    async def detect_image_intent(self, user_message: str) -> str | None:
        """
        Analyze a message to see if it's an implicit request for an image.
        Returns the extracted prompt if it is, otherwise None.
        """
        # Quick keyword pre-filter to save API calls
        keywords = [
            "draw", "make", "generate", "show", "visualize", "create", 
            "imagine", "picture", "image", "sketch", "paint", "art"
        ]
        if not any(word in user_message.lower() for word in keywords):
            return None

        system_prompt = (
            "You are an intent classifier. Your job is to determine if a user message is asking "
            "to generate, draw, or visualize an image. "
            "If the user is asking for an image, reply ONLY with the extracted image description/prompt. "
            "Do NOT enhance, expand, or add details to the prompt. Just extract the core description "
            "of what the user wants to see, using their own words as much as possible. "
            "If the user is NOT asking for an image, reply ONLY with 'NONE'. "
            "Be strict: only trigger if the intent is clearly about creating a new image. "
            "Ignore requests to talk about images, only trigger on requests to CREATE one."
        )
        
        try:
            # Use a low temperature for deterministic classification
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            payload = {
                "model": self._model,
                "messages": messages,
                "max_tokens": 100,
                "temperature": 0.0,
            }
            
            session = await self._get_session()
            async with session.post(self._api_url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = self._parse_response(data)
                    if content.upper() == "NONE" or not content:
                        return None
                    return content
        except Exception as e:
            log.warning(f"Failed to detect image intent: {e}")
            
        return None

    # ── Memory Extraction ─────────────────────────────────────────────────────

    async def extract_memories(self, user_message: str, author_name: str, context: list[str] | None = None, existing_memories: dict[str, str] | None = None) -> dict[str, str]:
        """
        Analyze the interaction to extract facts or preferences about the user.
        Returns a dictionary of {key: value} pairs to be stored in memory.
        """
        system_prompt = (
            "You are a memory extraction system for a Discord bot named Gork. "
            "Your job is to identify recurring preferences, explicit facts, or notable traits about a user. "
            "Focus on stable information: likes, dislikes, habits, occupation, location, or personality traits. "
            "Ignore transient info: current mood, temporary actions, or 'meta' talk about the bot unless it's a preference. "
            "Compare the conversation with 'Current Known Memories'. "
            "If you find NEW information or if a preference is REINFORCED/CHANGED, output a JSON object. "
            "Keys should be concise (e.g., 'favorite_food'). Values should be the summary of the fact. "
            "If no updates are needed, output ONLY '{}'. "
            "Do NOT output any conversational text, only the JSON object."
        )

        try:
            # Prepare context for the extraction
            context_text = ""
            if context:
                context_text = "## Recent Context\n" + "\n".join(context) + "\n\n"
            
            memories_text = ""
            if existing_memories:
                mem_lines = [f"- {k}: {v}" for k, v in existing_memories.items()]
                memories_text = "## Current Known Memories\n" + "\n".join(mem_lines) + "\n\n"
            
            user_input = f"{context_text}{memories_text}User ({author_name}): {user_message}"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]
            
            payload = {
                "model": self._model,
                "messages": messages,
                "max_tokens": 200,
                "temperature": 0.0,
            }
            
            session = await self._get_session()
            async with session.post(self._api_url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = self._parse_response(data)
                    # Try to parse the JSON content
                    try:
                        # Find the JSON part in case the model added some fluff
                        start = content.find('{')
                        end = content.rfind('}') + 1
                        if start != -1 and end != 0:
                            json_str = content[start:end]
                            extracted = json.loads(json_str)
                            if isinstance(extracted, dict):
                                return extracted
                    except json.JSONDecodeError:
                        log.warning(f"Failed to parse memory JSON: {content}")
        except Exception as e:
            log.warning(f"Memory extraction failed: {e}")
            
        return {}

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
        self, user_message: str, author_name: str, context: list[Any] | None = None, memories: dict[str, str] | None = None, images: list[dict] | None = None
    ) -> list[dict]:
        """Return the full messages list for the API call.
        
        Args:
            user_message: The user's text message.
            author_name: Display name of the user.
            context: List of recent messages (strings or dicts with 'author', 'content', 'images').
            memories: User memory dictionary.
            images: List of dicts with 'base64' and 'mime_type' keys for vision API.
        
        Returns:
            List of message dicts compatible with OpenAI vision API.
        """
        system_prompt = self._build_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]

        if memories:
            mem_lines = [f"- {k}: {v}" for k, v in memories.items()]
            messages.append({"role": "system", "content": f"## User Memories\n" + "\n".join(mem_lines) + "\n\n"})

        if context:
            # Build context content which may include images
            context_content: list[dict[str, Any]] = [{"type": "text", "text": "## Recent Conversation Context\n"}]
            
            for entry in context:
                if isinstance(entry, str):
                    context_content.append({"type": "text", "text": f"{entry}\n"})
                elif isinstance(entry, dict):
                    author = entry.get("author", "Unknown")
                    content_text = entry.get("content", "")
                    context_content.append({"type": "text", "text": f"{author}: {content_text}\n"})
                    
                    # Add images from this context message if any
                    msg_images = entry.get("images", [])
                    for img in msg_images:
                        context_content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{img['mime_type']};base64,{img['base64']}",
                            },
                        })
            
            messages.append({"role": "system", "content": context_content})

        user_prompt = (
            f"[Responding to Discord user '{author_name}']\n\n{user_message}"
        )
        
        # Build user message content
        content: list = [{"type": "text", "text": user_prompt}]
        
        # Add images if provided
        if images:
            for image_info in images:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image_info['mime_type']};base64,{image_info['base64']}",
                    },
                })
        
        messages.append({"role": "user", "content": content})
        return messages

    # ── API call ──────────────────────────────────────────────────────────────

    async def generate_response(
        self, user_message: str, author_name: str = "User", context: list[Any] | None = None, memories: dict[str, str] | None = None, images: list[dict] | None = None
    ) -> str:
        """
        Send a prompt to the Hack Club AI proxy and return the text reply.

        Args:
            user_message: The cleaned message from the Discord user.
            author_name:  Display name of the Discord user (for context).
            context: List of recent messages (strings or dicts).
            memories: Dict of user memories as key-value pairs.
            images: List of dicts with 'base64' and 'mime_type' for vision API.

        Returns:
            The AI-generated response as a plain string.

        Raises:
            RuntimeError: On non-200 HTTP status or malformed response.
        """
        messages = self._build_messages(user_message, author_name, context, memories, images)
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": 1024,
            "temperature": self._personality.get("temperature", 0.85),
        }

        log.debug(f"Sending request to Hack Club AI | model={self._model}" + (f" | images={len(images)}" if images else ""))

        max_retries = 3
        for attempt in range(max_retries):
            try:
                session = await self._get_session()
                async with session.post(
                    self._api_url, json=payload
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise RuntimeError(
                            f"Hack Club AI returned HTTP {resp.status}: {body[:300]}"
                        )

                    data: dict[str, Any] = await resp.json()
                    return self._parse_response(data)

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # exponential backoff: 1, 2, 4 seconds
                    log.warning(f"Attempt {attempt + 1} failed: {exc}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    log.error(f"All {max_retries} attempts failed. Last error: {exc}")
                    raise RuntimeError(f"Network error after {max_retries} attempts: {exc}") from exc

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
            raise RuntimeError(f"Could not parse AI response: {exc}. Full data: {data}") from exc
