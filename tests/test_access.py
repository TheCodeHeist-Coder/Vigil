from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
import pytest

from services.gateway.access import COOKIE, AccessKey

KEY = "s3cret-key"
TUNNEL = {"x-forwarded-for": "203.0.113.9", "x-forwarded-proto": "https"}


async def page(_):
    return PlainTextResponse("private")


async def socket(ws):
    await ws.accept()
    await ws.send_text("live")
    await ws.close()


def client(key: str = KEY, host: str = "127.0.0.1") -> TestClient:
    app = Starlette(routes=[Route("/", page), Route("/api/manual", page), WebSocketRoute("/ws/live", socket)])
    app.add_middleware(AccessKey, key=key)
    return TestClient(app, client=(host, 5000), follow_redirects=False)


def test_this_laptop_needs_no_key():
    assert client().get("/api/manual").text == "private"


def test_public_request_without_a_key_is_refused():
    response = client().get("/api/manual", headers=TUNNEL)
    assert response.status_code == 401
    assert "private" in response.text and KEY not in response.text


def test_wrong_key_is_refused():
    assert client().get("/?key=guess", headers=TUNNEL).status_code == 401


def test_right_key_sets_a_cookie_and_removes_the_key_from_the_address():
    response = client().get(f"/?key={KEY}", headers=TUNNEL)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie


def test_cookie_opens_pages_and_the_live_socket():
    c = client()
    c.cookies.set(COOKIE, KEY)
    assert c.get("/api/manual", headers=TUNNEL).text == "private"
    with c.websocket_connect("/ws/live", headers=TUNNEL) as ws:
        assert ws.receive_text() == "live"


def test_public_socket_without_a_cookie_is_refused():
    with pytest.raises(WebSocketDisconnect):
        with client().websocket_connect("/ws/live", headers=TUNNEL):
            pass


def test_another_device_on_the_network_needs_the_key():
    assert client(host="10.229.101.50").get("/api/manual").status_code == 401


def test_no_key_configured_leaves_the_app_open():
    assert client(key="").get("/api/manual", headers=TUNNEL).text == "private"
