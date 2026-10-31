"""Client for Meko's MCP endpoint, which holds agent memory, conversations and traces.

Follows the reference client in yugabyte/canned-agents (Apache-2.0).
"""

import itertools
import json
from typing import Any

import httpx

PROTOCOL_VERSION = "2025-06-18"


class MekoError(RuntimeError):
    pass


class MekoClient:
    def __init__(self, url: str, api_key: str, timeout: float = 30.0, transport: httpx.BaseTransport | None = None) -> None:
        self.url = url
        self.api_key = api_key
        self.session_id: str | None = None
        self.ready = False
        self.ids = itertools.count(1)
        self.client = httpx.Client(timeout=timeout, transport=transport)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "vigil/0.1",  # Meko rejects requests with no User-Agent
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    @staticmethod
    def _parse_sse(body: str, expected_id: int) -> dict[str, Any]:
        last: dict[str, Any] | None = None
        for line in body.splitlines():
            if not line.startswith("data:"):
                continue
            try:
                data = json.loads(line[5:].strip())
            except ValueError:
                continue
            if ("result" in data or "error" in data) and str(data.get("id")) == str(expected_id):
                return data
            last = data
        if last is None:
            raise MekoError("no parseable SSE response")
        return last

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        request_id = next(self.ids)
        response = self.client.post(
            self.url,
            headers=self._headers(),
            json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
        )
        session = response.headers.get("mcp-session-id")
        if session:
            self.session_id = session
        response.raise_for_status()
        is_sse = "text/event-stream" in response.headers.get("content-type", "")
        payload = self._parse_sse(response.text, request_id) if is_sse else response.json()
        if payload.get("error"):
            raise MekoError(f"{payload['error'].get('code')}: {payload['error'].get('message')}")
        return payload.get("result")

    def _ensure_ready(self) -> None:
        if self.ready:
            return
        self._rpc(
            "initialize",
            {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "vigil", "version": "0.1.0"}},
        )
        self.client.post(self.url, headers=self._headers(), json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.ready = True

    def tools(self) -> list[str]:
        self._ensure_ready()
        return [tool["name"] for tool in self._rpc("tools/list", {}).get("tools", [])]

    def call(self, tool: str, /, **arguments: Any) -> Any:
        self._ensure_ready()
        arguments = {k: v for k, v in arguments.items() if v is not None}
        result = self._rpc("tools/call", {"name": tool, "arguments": arguments}) or {}
        texts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
        if result.get("isError"):
            raise MekoError("\n".join(texts) or f"{tool} failed")
        if not texts:
            return result
        try:
            parsed: Any = json.loads(texts[0])
        except ValueError:
            return texts[0]
        while isinstance(parsed, str):  # some tools double-encode their result
            try:
                parsed = json.loads(parsed)
            except ValueError:
                break
        if isinstance(parsed, dict) and parsed.get("error"):  # some failures arrive as normal data
            raise MekoError(f"{tool}: {parsed['error']} {parsed.get('detail', '')}")
        return parsed

    def close(self) -> None:
        self.client.close()
