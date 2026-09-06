"""Minimal async client for an OpenAI-compatible vision chat endpoint (vLLM).

Only what the KI-Import needs: send one prompt with up to a few images and
get back a JSON object that conforms to a given JSON schema.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx

from mv_hofki.core.config import settings

# vLLM is started with --limit-mm-per-prompt '{"image": 5}'
MAX_IMAGES_PER_REQUEST = 5


class LlmError(Exception):
    """The model endpoint failed or returned something unusable."""


def image_data_url(png_bytes: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64," + base64.b64encode(png_bytes).decode("ascii")


class LlmClient:
    """Thin wrapper around ``POST {base_url}/chat/completions``.

    ``transport`` is exposed so tests can inject an ``httpx.MockTransport``.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL
        self.timeout = timeout or settings.LLM_TIMEOUT_SECONDS
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout, transport=self._transport)

    async def list_models(self) -> list[str]:
        """Return served model names; useful as a connectivity check."""
        async with self._client() as client:
            try:
                resp = await client.get(f"{self.base_url}/models")
            except httpx.HTTPError as e:
                raise LlmError(f"LLM-Endpunkt nicht erreichbar: {e}") from e
        if resp.status_code != 200:
            raise LlmError(f"LLM-Endpunkt antwortete mit HTTP {resp.status_code}")
        return [m["id"] for m in resp.json().get("data", [])]

    def build_payload(
        self,
        prompt: str,
        images: list[bytes],
        schema: dict[str, Any],
        schema_name: str = "extraction",
        system: str | None = None,
        max_tokens: int = 4000,
    ) -> dict[str, Any]:
        if len(images) > MAX_IMAGES_PER_REQUEST:
            raise LlmError(
                f"Höchstens {MAX_IMAGES_PER_REQUEST} Bilder pro Anfrage, "
                f"{len(images)} übergeben"
            )
        content: list[dict[str, Any]] = [
            {"type": "image_url", "image_url": {"url": image_data_url(img)}}
            for img in images
        ]
        content.append({"type": "text", "text": prompt})
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": content})
        return {
            "model": self.model,
            "temperature": 0,
            "max_tokens": max_tokens,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema},
            },
            # Qwen3 thinking mode costs tokens and time; structured extraction
            # works better without it.
            "chat_template_kwargs": {"enable_thinking": False},
        }

    async def chat_json(
        self,
        prompt: str,
        images: list[bytes],
        schema: dict[str, Any],
        schema_name: str = "extraction",
        system: str | None = None,
        max_tokens: int = 4000,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Send prompt + images, return ``(parsed_json, usage)``."""
        payload = self.build_payload(
            prompt, images, schema, schema_name, system, max_tokens
        )
        async with self._client() as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/chat/completions", json=payload
                )
            except httpx.HTTPError as e:
                raise LlmError(f"LLM-Endpunkt nicht erreichbar: {e}") from e

        if resp.status_code != 200:
            detail = resp.text[:500]
            raise LlmError(
                f"LLM-Endpunkt antwortete mit HTTP {resp.status_code}: {detail}"
            )

        body = resp.json()
        try:
            choice = body["choices"][0]
            text = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LlmError(f"Unerwartete Antwortstruktur: {body!r:.300}") from e

        if choice.get("finish_reason") == "length":
            raise LlmError(
                "Antwort wurde abgeschnitten (max_tokens erreicht); "
                "Seite ist zu umfangreich für eine Anfrage"
            )
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            raise LlmError(f"Antwort ist kein gültiges JSON: {text[:300]!r}") from e
        if not isinstance(parsed, dict):
            raise LlmError("Antwort ist kein JSON-Objekt")
        return parsed, body.get("usage") or {}
