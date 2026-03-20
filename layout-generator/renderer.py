"""Minimal renderer client — calls the local api-render Next.js server."""

import base64
import os

import requests


class ObelloRenderer:
    def __init__(self, endpoint: str | None = None):
        self.endpoint = endpoint or os.getenv("OBELLO_RENDERER_ENDPOINT", "http://localhost:3000")
        self.timeout = float(os.getenv("OBELLO_RENDERER_TIMEOUT", "60"))
        self._session = requests.Session()

    def render(self, layout: dict) -> bytes:
        url = self.endpoint.rstrip("/") + "/api/render/preview"
        resp = self._session.post(url, json={"data": layout}, timeout=self.timeout)
        resp.raise_for_status()
        data_url = resp.json().get("dataUrl")
        if not data_url or "," not in data_url:
            raise RuntimeError(f"Unexpected render response: {resp.text[:200]}")
        _, encoded = data_url.split(",", 1)
        return base64.b64decode(encoded)
