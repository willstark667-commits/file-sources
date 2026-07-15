"""
odysseus_client.py — Thin client that lets Ashley AI Studio call a running
Odysseus instance as a backend LLM/agent service over its REST API.

Verified against Odysseus source (odysseus-dev):
  - src/request_models.py:ChatRequest   (message, session, attachments,
    use_web, use_research, time_filter, preset_id)
  - routes/chat_routes.py               (POST /api/chat, POST /api/chat_stream)
  - routes/session_routes.py            (POST /session to create a session)
  - routes/api_token_routes.py          (Bearer token auth, scoped: "chat")

Usage from Ashley's LLMBridge:

    from odysseus_client import OdysseusClient

    client = OdysseusClient(base_url="http://127.0.0.1:7000", token="odys_...")
    session_id = client.create_session(endpoint_url="http://127.0.0.1:11434", model="llama3.1")
    reply = client.chat(session_id, "Summarize this bug report...")
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional, Iterator


class OdysseusError(RuntimeError):
    """Raised on any non-2xx response or connection failure to Odysseus."""


@dataclass
class OdysseusClient:
    base_url: str = "http://127.0.0.1:7000"
    token: Optional[str] = None          # Bearer API token, scope "chat" minimum
    timeout: float = 60.0

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        url = self.base_url.rstrip("/") + path
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise OdysseusError(f"Odysseus API {e.code} on {path}: {detail}") from e
        except urllib.error.URLError as e:
            raise OdysseusError(
                f"Could not reach Odysseus at {url} ({e.reason}). "
                f"Is it running? (launch-windows.ps1 / docker compose up)"
            ) from e

    def health(self) -> bool:
        """Quick reachability check — returns False instead of raising."""
        try:
            self._request("GET", "/api/search?q=ping")
            return True
        except OdysseusError:
            return False

    def create_session(self, endpoint_url: str, model: str = "", name: str = "",
                        rag: bool = False) -> str:
        """
        Create an Odysseus chat session bound to an LLM endpoint (e.g. a local
        Ollama server, or any OpenAI-compatible endpoint Odysseus is configured
        to reach). Returns the session id to pass into chat().
        """
        result = self._request("POST", "/session", {
            "name": name,
            "endpoint_url": endpoint_url,
            "model": model,
            "rag": rag,
        })
        sid = result.get("session_id") or result.get("id") or result.get("session")
        if not sid:
            raise OdysseusError(f"Unexpected /session response, no id found: {result}")
        return sid

    def chat(self, session_id: str, message: str, *, use_web: bool = False,
              use_research: bool = False, attachments: Optional[list] = None,
              preset_id: Optional[str] = None) -> str:
        """Non-streaming chat call. Returns the assistant's reply text."""
        result = self._request("POST", "/api/chat", {
            "message": message,
            "session": session_id,
            "attachments": attachments or [],
            "use_web": use_web,
            "use_research": use_research,
            "preset_id": preset_id,
        })
        # response_model=Dict[str, str] on the Odysseus side — reply text is
        # typically under "response" or "message"; check both defensively.
        return result.get("response") or result.get("message") or json.dumps(result)


if __name__ == "__main__":
    # Manual smoke test — requires a running Odysseus instance.
    import sys
    c = OdysseusClient(base_url="http://127.0.0.1:7000", token=None)
    if not c.health():
        print("Odysseus not reachable at", c.base_url)
        sys.exit(1)
    print("Odysseus reachable.")
