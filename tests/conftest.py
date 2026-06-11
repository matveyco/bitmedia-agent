import pytest
import yaml

LIMITS = {
    "daily_spend_cap": 30,
    "daily_refill_cap": 30,
    "max_single_refill": 30,
    "group_daily_limit_min": 50,
    "group_daily_limit_max": 60,
    "max_cpc_bid": 0.50,
    "max_cpm_bid": 1.00,
    "reserve_balance": 400,
    "velocity_pause_factor": 1.3,
}


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """Isolated workspace with known limits."""
    monkeypatch.setenv("BITMEDIA_WORKSPACE", str(tmp_path))
    (tmp_path / "config").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "config" / "limits.yaml").write_text(yaml.safe_dump(LIMITS))
    return tmp_path


class FakeClient:
    """Records every call; serves canned responses by (method, path)."""

    def __init__(self, routes: dict | None = None):
        self.routes = routes or {}
        self.calls: list[tuple] = []

    def request(self, method, path, **kw):
        self.calls.append((method, path, kw))
        handler = self.routes.get((method, path))
        if callable(handler):
            return handler(kw)
        return handler

    def get(self, path, **params):
        return self.request("GET", path, params=params)

    def post(self, path, json=None, *, data=None, files=None):
        return self.request("POST", path, json=json, data=data, files=files)

    def called(self, method, path) -> list[tuple]:
        return [c for c in self.calls if c[0] == method and c[1] == path]


@pytest.fixture
def fake_client():
    return FakeClient()
