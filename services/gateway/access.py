"""Keeps a public link private. Opening it once with ?key=... sets a cookie for that device.

Requests from this laptop need no key. A tunnel also connects from this laptop, but it adds
forwarding headers, which is how the two are told apart.
"""

import hmac

from starlette.requests import HTTPConnection
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

COOKIE = "vigil_key"
WEEK_SECONDS = 7 * 24 * 60 * 60
FORWARDED = {"x-forwarded-for", "cf-connecting-ip", "x-real-ip", "forwarded"}

LOCKED = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vigil</title><body style="margin:0;display:grid;place-content:center;min-height:100vh;padding:24px;
font:16px system-ui;text-align:center;color:#101828;background:#f4f5f7"><h1 style="font-size:22px;margin:0 0 6px">This link is private</h1>
<p style="margin:0;color:#667085">Ask your team for the full Vigil link.</p></body>"""


def is_local(scope: Scope, connection: HTTPConnection) -> bool:
    host = connection.client.host if connection.client else ""
    return host in ("127.0.0.1", "::1") and not FORWARDED & set(connection.headers.keys())


class AccessKey:
    def __init__(self, app: ASGIApp, key: str) -> None:
        self.app = app
        self.key = key

    def _matches(self, value: str | None) -> bool:
        return bool(value) and hmac.compare_digest(value, self.key)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self.key or scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        connection = HTTPConnection(scope)
        if is_local(scope, connection) or self._matches(connection.cookies.get(COOKIE)):
            await self.app(scope, receive, send)
        elif scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
        elif self._matches(connection.query_params.get("key")):
            # The browser keeps the #/phone part of the address across this redirect.
            response = RedirectResponse(scope["path"], status_code=303)
            secure = connection.headers.get("x-forwarded-proto") == "https"
            response.set_cookie(COOKIE, self.key, max_age=WEEK_SECONDS, httponly=True, secure=secure, samesite="lax")
            await response(scope, receive, send)
        else:
            await HTMLResponse(LOCKED, status_code=401)(scope, receive, send)
