"""
image_gen.py — Hack Club AI Image Generation
Uses the chat completions endpoint with google/gemini-2.5-flash-image
(the only image model allowed by the Hack Club proxy).

NOTE: The `modalities` parameter is NOT supported through the Hack Club
proxy — it causes a 404. The model itself handles image output natively
when addressed with an image-generation prompt.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import concurrent.futures
from typing import Any

import aiohttp

log = logging.getLogger("gork.image_gen")

IMAGE_API_URL   = "https://ai.hackclub.com/proxy/v1/chat/completions"
IMAGE_MODEL     = "google/gemini-2.5-flash-image"   # only allowed image model
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=180)    # image gen can be slow


class ImageGenClient:
    """
    Async wrapper for Hack Club AI image generation.
    Accepts a plain text prompt, returns PNG bytes.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        api_key = config.get("hackclub_api_key", "")
        if not api_key:
            raise ValueError("hackclub_api_key is required for image generation.")
        self._api_key = api_key
        self._image_style = config.get("image_style", "")
        self._model = config.get("image_model", IMAGE_MODEL)
        self._api_url = config.get("api_url", IMAGE_API_URL)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
                timeout=REQUEST_TIMEOUT,
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def generate(self, prompt: str) -> bytes:
        """
        Generate an image from a text prompt.

        Args:
            prompt: Natural language description of the image.

        Returns:
            Raw PNG bytes.

        Raises:
            RuntimeError: On API error or if no image is returned.
        """
        # Do NOT send `modalities` — the Hack Club proxy rejects it with 404.
        # The gemini-2.5-flash-image model generates images natively.

        # Prepend the image style from personality config if set.
        # Format: "Style: <style>. Subject: <user prompt>"
        if self._image_style:
            full_prompt = f"Style: {self._image_style}. Subject: {prompt}"
        else:
            full_prompt = prompt

        # Add safety filter to prevent NSFW content
        safety_prefix = "Generate a non NSFW image"
        full_prompt = safety_prefix + full_prompt

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "user", "content": full_prompt}
            ],
        }

        log.info(f"Requesting image | model={self._model} prompt='{prompt[:80]}'")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                session = await self._get_session()
                async with session.post(self._api_url, json=payload) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise RuntimeError(
                            f"Image API returned HTTP {resp.status}: {body[:400]}"
                        )
                    data: dict[str, Any] = await resp.json()
                break  # success, exit retry loop
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    log.warning(f"Image gen attempt {attempt + 1} failed: {exc}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise RuntimeError(f"Network error during image gen after {max_retries} attempts: {exc}") from exc

        # Log the raw response keys to help debug if parsing fails
        log.debug(f"Image API response keys: {list(data.get('choices', [{}])[0].get('message', {}).keys())}")

        return await self._extract_image_bytes(data)

    @staticmethod
    async def _extract_image_bytes(data: dict[str, Any]) -> bytes:
        """
        Extract image bytes from the API response.

        Tries three known response shapes in order:

        Shape A — dedicated "images" array:
          message.images[0].image_url.url = "data:image/png;base64,..."

        Shape B — inline content array with image_url blocks:
          message.content = [{"type": "image_url", "image_url": {"url": "..."}}]

        Shape C — content array with inline_data blocks (Gemini native format):
          message.content = [{"type": "image", "inline_data": {"data": "<base64>", "mime_type": "image/png"}}]
        """
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, ImageGenClient._extract_image_bytes_sync, data)
        except (KeyError, IndexError, TypeError) as exc:
            log.error(f"Unexpected image response shape: {data}")
            raise RuntimeError(f"Could not parse image response: {exc}") from exc

    @staticmethod
    def _extract_image_bytes_sync(data: dict[str, Any]) -> bytes:
        """
        Synchronous helper for _extract_image_bytes.
        """
        try:
            message = data["choices"][0]["message"]

            # ── Shape A ───────────────────────────────────────────────────────
            images = message.get("images") or []
            if images:
                url: str = images[0]["image_url"]["url"]
                if "," in url:
                    url = url.split(",", 1)[1]
                return base64.b64decode(url)

            # ── Shapes B & C (inline content array) ───────────────────────────
            content = message.get("content") or []
            if isinstance(content, list):
                for block in content:
                    btype = block.get("type", "")

                    # Shape B — image_url block
                    if btype == "image_url":
                        url = block["image_url"]["url"]
                        if "," in url:
                            url = url.split(",", 1)[1]
                        return base64.b64decode(url)

                    # Shape C — inline_data block (raw Gemini format)
                    if btype == "image" and "inline_data" in block:
                        return base64.b64decode(block["inline_data"]["data"])

            # Nothing found — log the full response to help diagnose
            log.error(f"Could not find image in response. Full response: {data}")
            raise RuntimeError(
                "No image found in API response. "
                "The model may have refused the prompt, or the response format has changed. "
                "Check bot logs for the full response."
            )

        except (KeyError, IndexError, TypeError) as exc:
            log.error(f"Unexpected image response shape: {data}")
            raise RuntimeError(f"Could not parse image response: {exc}") from exc
