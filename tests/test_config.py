"""Shipped templates must always parse and validate — CI keeps them honest."""
from importlib import resources

import pytest
import yaml

from bitmedia_agent.configcheck import validate_campaign, validate_limits


def _load_template(name):
    return yaml.safe_load((resources.files("bitmedia_agent") / "templates" / name).read_text())


def test_limits_template_valid():
    validate_limits(_load_template("limits.yaml"))


def test_campaign_template_valid():
    validate_campaign(_load_template("campaign.yaml"))


def test_validator_catches_missing_source_macro():
    cfg = _load_template("campaign.yaml")
    cfg["landing"]["utm_content"] = "{size}-static"
    with pytest.raises(ValueError, match="source"):
        validate_campaign(cfg)


def test_validator_catches_long_text_ads():
    cfg = _load_template("campaign.yaml")
    cfg["text_ads"] = [{"key": "x", "title": "T" * 36, "description1": "a",
                        "description2": "b"}]
    with pytest.raises(ValueError, match="35"):
        validate_campaign(cfg)


def test_limits_validator_rejects_inconsistent_caps():
    lim = _load_template("limits.yaml")
    lim["max_single_refill"] = lim["daily_refill_cap"] + 10
    with pytest.raises(ValueError, match="max_single_refill"):
        validate_limits(lim)
