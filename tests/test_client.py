import json

import httpx
import pytest

from bitmedia_agent.bitmedia.client import BASE_URL, BitmediaError, Client


def make_client(handler):
    c = Client(api_key="test-key")
    c._http = httpx.Client(transport=httpx.MockTransport(handler), base_url=BASE_URL,
                           headers={"X-API-Key": "test-key"})
    return c


def test_success_envelope_unwrapped():
    def handler(req):
        return httpx.Response(200, json={"success": True, "data": {"usd": 5}, "error": ""})
    assert make_client(handler).get("/api/user/balance") == {"usd": 5}


def test_error_field_raised():
    def handler(req):
        return httpx.Response(400, json={"success": False, "data": None,
                                         "error": "Bid must be >= 0.1"})
    with pytest.raises(BitmediaError, match="Bid must be"):
        make_client(handler).post("/api/groups/create", {})


def test_auth_layer_message_field_raised():
    def handler(req):
        return httpx.Response(401, json={"message": "Not authorized to access this resource."})
    with pytest.raises(BitmediaError, match="Not authorized"):
        make_client(handler).get("/api/user/balance")


def test_non_json_body_raises_with_status():
    def handler(req):
        return httpx.Response(502, text="<html>bad gateway</html>")
    with pytest.raises(BitmediaError, match="502"):
        make_client(handler).get("/api/user/balance")


def test_429_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    state = {"n": 0}

    def handler(req):
        state["n"] += 1
        if state["n"] < 3:
            return httpx.Response(429, json={"message": "Too many requests"})
        return httpx.Response(200, json={"success": True, "data": "ok", "error": ""})

    assert make_client(handler).get("/api/user/balance") == "ok"
    assert state["n"] == 3


def test_api_key_sent_as_header():
    def handler(req):
        assert req.headers["X-API-Key"] == "test-key"
        return httpx.Response(200, json={"success": True, "data": json.loads("{}"),
                                         "error": ""})
    make_client(handler).get("/api/user/balance")
