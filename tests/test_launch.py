import pytest
import yaml

from bitmedia_agent import ledger
from bitmedia_agent.configcheck import validate_campaign
from bitmedia_agent.launch import banner_source, click_url, creative_title, launch
from tests.conftest import FakeClient

CFG = {
    "campaign": {"name": "test-camp", "currency": "USD", "initial_funding": 30},
    "landing": {
        "base_url": "https://example.com/lp",
        "static_params": {"utm_source": "bitmedia", "utm_medium": "cpc",
                          "utm_campaign": "test"},
        "utm_content": "{size}-{source}",
    },
    "creative_title_pattern": "{campaign}-{size}-{group}",
    "defaults": {
        "type": "native_cpc", "bid_strategy": "static", "countries": ["US"],
        "vpn_traffic": "excluded", "ad_rerun": 72,
        "frequency": {"enabled": False}, "display_time": {"from": 0, "to": 24},
        "pacing_split": False,
    },
    "groups": [{
        "name": "mobile", "bid": 0.45, "daily_limit": 50,
        "mobile_os": {"android": True, "ios": True, "winmobile": False, "others": True},
        "desktop_os": {"windows": False, "linux": False, "macos": False, "others": False},
        "creatives": ["300x250"],
    }],
    "banners_dir": "banners",
    "banner_pattern": "ad-banner-{size}.png",
    "text_display_url": "example.com",
    "text_ads": [{"key": "txt-a", "title": "Headline", "description1": "Line one.",
                  "description2": "Line two."}],
}


def test_click_url_keeps_source_macro_literal():
    url = click_url(CFG, "300x250")
    assert "{source}" in url
    assert "300x250-%7Bsource%7D" not in url
    assert url.startswith("https://example.com/lp?")
    assert "utm_content=300x250-%7B" not in url


def test_click_url_substitutes_size():
    assert "utm_content=728x90-" in click_url(CFG, "728x90")


def test_creative_title_pattern():
    assert creative_title(CFG, "300x250", "mobile") == "test-camp-300x250-mobile"


def test_banner_source_default_set_keeps_bare_token(ws):
    token, path = banner_source(CFG, "300x250")
    assert token == "300x250"  # unchanged token = ledger idempotency across upgrades
    assert str(path).endswith("banners/ad-banner-300x250.png")


def test_banner_source_named_set(ws):
    cfg = {**CFG, "banner_sets": {"ar": {"dir": "banners-ar"}}}
    token, path = banner_source(cfg, "ar:300x250")
    assert token == "ar-300x250"
    assert str(path).endswith("banners-ar/ad-banner-300x250.png")


def test_validator_rejects_undefined_banner_set():
    cfg = yaml.safe_load(yaml.safe_dump(CFG))
    cfg["groups"][0]["creatives"] = ["xx:300x250"]
    with pytest.raises(ValueError, match="undefined banner set"):
        validate_campaign(cfg)


def test_launch_fails_clearly_on_missing_banner_file(ws):
    cfg = yaml.safe_load(yaml.safe_dump(CFG))
    cfg["groups"][0]["creatives"] = ["728x90"]  # file not created by _setup_workspace
    (ws / "config" / "campaign.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True))
    (ws / "banners").mkdir()
    with pytest.raises(FileNotFoundError, match="728x90"):
        launch(client=FakeClient(_launch_routes()))


def _launch_routes():
    counter = {"n": 0}

    def next_id(_kw):
        counter["n"] += 1
        return f"cr-{counter['n']}"

    return {
        ("GET", "/api/groups/recommended-bid"): {"min": 0.4, "max": 0.7, "current": 0.5},
        ("POST", "/api/campaigns/create"): "camp-1",
        ("POST", "/api/groups/create"): "grp-1",
        ("POST", "/api/groups/set-group-targeting"): None,
        ("POST", "/api/groups/group-limit"): None,
        ("GET", "/api/groups/group-limit"): {"exists": True, "amount": 50},
        ("POST", "/api/creatives/create-image"): next_id,
        ("POST", "/api/creatives/upload-images"): None,
        ("POST", "/api/creatives/create-text"): next_id,
        ("GET", "/api/user/balance"): {"usd": 1000},
        ("POST", "/api/campaigns/usd-refill-campaign"): None,
        ("POST", "/api/campaigns/activate-campaign"): None,
        ("POST", "/api/groups/activate-group"): None,
    }


def _setup_workspace(ws):
    (ws / "config" / "campaign.yaml").write_text(yaml.safe_dump(CFG, allow_unicode=True))
    (ws / "banners").mkdir()
    (ws / "banners" / "ad-banner-300x250.png").write_bytes(b"\x89PNG fake")


def test_launch_builds_everything(ws):
    _setup_workspace(ws)
    client = FakeClient(_launch_routes())
    out = launch(client=client)
    assert out["campaign_id"] == "camp-1"
    assert out["groups"] == {"mobile": "grp-1"}
    assert len(out["creatives"]) == 2  # one image + one text ad
    assert client.called("POST", "/api/campaigns/usd-refill-campaign")
    assert out["activated"] is True


def test_launch_is_idempotent(ws):
    _setup_workspace(ws)
    launch(client=FakeClient(_launch_routes()))
    creates_before = len(ledger.entries("creative.create"))

    client2 = FakeClient(_launch_routes())
    out2 = launch(client=client2)

    assert out2["creatives"] == []  # nothing re-created
    assert len(ledger.entries("creative.create")) == creates_before
    assert not client2.called("POST", "/api/campaigns/create")
    assert not client2.called("POST", "/api/groups/create")
    assert not client2.called("POST", "/api/creatives/create-image")
    # funding not repeated either
    assert not client2.called("POST", "/api/campaigns/usd-refill-campaign")
