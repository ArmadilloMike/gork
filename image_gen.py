"""
image_gen.py — Hack Club AI Image Generation
Isolated module for generating images via the Hack Club AI proxy.
Returns raw bytes so the caller can send them however it likes.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

import aiohttp

log = logging.getLogger("gork.image_gen")

IMAGE_API_URL = "https://ai.hackclub.com/proxy/v1/chat/completions"
IMAGE_MODEL   = "google/gemini-2.5-flash-image-preview"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=60)  # image gen is slow


class ImageGenClient:
    """
    Async wrapper for Hack Club AI image generation.
    Accepts a plain text prompt, returns PNG bytes.
    """

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("hackclub_api_key is required for image generation.")
        self._api_key = api_key
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
        payload: dict[str, Any] = {
            "model": IMAGE_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "modalities": ["image", "text"],
            "stream": False,
        }

        log.info(f"Requesting image generation | prompt='{prompt[:80]}...'")
        session = await self._get_session()

        try:
            async with session.post(IMAGE_API_URL, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(
                        f"Image API returned HTTP {resp.status}: {body[:300]}"
                    )
                data: dict[str, Any] = await resp.json()
        except aiohttp.ClientError as exc:
            raise RuntimeError(f"Network error during image gen: {exc}") from exc

        return self._extract_image_bytes(data)

    @staticmethod
    def _extract_image_bytes(data: dict[str, Any]) -> bytes:
        """
        Pull the base64 image out of the API response and decode it.

        Expected shape:
          choices[0].message.images[0].image_url.url = "data:image/png;base64,..."
        """
        try:
            message = data["choices"][0]["message"]
            images  = message.get("images", [])

            if not images:
                raise RuntimeError(
                    "No images in API response. The model may have refused "
                    "the prompt or returned text only."
                )

            url: str = images[0]["image_url"]["url"]

            # Strip the data URI prefix if present: "data:image/png;base64,<data>"
            if "," in url:
                url = url.split(",", 1)[1]

            return base64.b64decode(url)

        except (KeyError, IndexError, TypeError) as exc:
            log.error(f"Unexpected image response shape: {data}")
            raise RuntimeError(f"Could not parse image response: {exc}") from exc