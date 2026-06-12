"""Builds the campaign declared in config/campaign.yaml. Idempotent: re-running
resumes from the ledger instead of duplicating entities."""
from urllib.parse import urlencode

import yaml

from . import ledger, workspace
from .bitmedia import groups as g
from .bitmedia.client import BitmediaError, Client
from .configcheck import creative_title, creative_token, validate_campaign
from .guard import Guard


def _find(action: str, match: dict) -> str | None:
    for e in ledger.entries(action):
        if all(e["params"].get(k) == v for k, v in match.items()):
            if isinstance(e["result"], str):
                return e["result"]
            if isinstance(e["result"], dict) and e["result"].get("creative_id"):
                return e["result"]["creative_id"]
    return None


def click_url(cfg: dict, size: str) -> str:
    land = cfg["landing"]
    params = dict(land["static_params"])
    params["utm_content"] = land["utm_content"].replace("{size}", size)
    # urlencode would escape the {source} macro braces — keep them literal
    return land["base_url"] + "?" + urlencode(params).replace("%7Bsource%7D", "{source}")


def banner_source(cfg: dict, entry: str) -> tuple[str, "object"]:
    """Resolve a group creatives entry to (token, image path).

    Plain entries ("300x250") use the default top-level banners_dir/banner_pattern
    and keep the bare size as token — stable across upgrades so ledger idempotency
    holds. Prefixed entries ("ar:300x250") resolve via banner_sets[<key>] and use
    "<key>-<size>" as the token in titles and utm_content.
    """
    if ":" in entry:
        set_key, size = entry.split(":", 1)
        spec = (cfg.get("banner_sets") or {})[set_key]
        directory = spec["dir"]
        pattern = spec.get("pattern", cfg.get("banner_pattern", "ad-banner-{size}.png"))
    else:
        size = entry
        directory, pattern = cfg["banners_dir"], cfg["banner_pattern"]
    path = workspace.root() / directory / pattern.replace("{size}", size)
    return creative_token(entry), path


def launch(fund: bool = True, activate: bool = True, client: Client | None = None) -> dict:
    cfg = yaml.safe_load(workspace.campaign_path().read_text())
    validate_campaign(cfg)
    client = client or Client()
    guard = Guard(client)
    out = {"groups": {}, "creatives": [], "warnings": []}

    # recommended bids for visibility (logged, not auto-applied)
    for dev in ("mobile", "desktop"):
        try:
            rec = g.recommended_bid(client, devices=dev, countries=",".join(
                cfg["defaults"]["countries"]), group_type=cfg["defaults"]["type"])
            out[f"recommended_bid_{dev}"] = rec
            ledger.append("info.recommended_bid", {"devices": dev}, rec)
        except BitmediaError as e:
            out["warnings"].append(f"recommended-bid {dev}: {e}")

    camp = cfg["campaign"]
    cid = _find("campaign.create", {"name": camp["name"]})
    if not cid:
        cid = guard.create_campaign(camp["name"], camp.get("currency", "USD"))
    out["campaign_id"] = cid

    d = cfg["defaults"]
    for spec in cfg["groups"]:
        gid = _find("group.create", {"name": spec["name"], "campaign_id": cid})
        if not gid:
            gid = guard.create_group(spec["name"], cid, group_type=d["type"],
                                     bid=spec["bid"], daily_limit=spec["daily_limit"],
                                     bid_strategy=d["bid_strategy"])
        out["groups"][spec["name"]] = gid

        targeting = dict(
            countries=d["countries"], mobile_os=spec["mobile_os"],
            desktop_os=spec["desktop_os"], vpn_traffic=d["vpn_traffic"],
            frequency=d.get("frequency"), ad_rerun=d.get("ad_rerun", 72),
            display_time=d.get("display_time"), pacing_split=d.get("pacing_split", False),
        )
        try:
            guard.set_targeting(gid, **targeting)
        except BitmediaError as e:
            if "frequency" in str(e).lower():
                targeting["frequency"] = {"enabled": False}
                guard.set_targeting(gid, **targeting)
                out["warnings"].append(f"{spec['name']}: frequency capping unavailable ({e})")
            else:
                raise
        guard.set_group_limit(gid, spec["daily_limit"])

        for entry in spec["creatives"]:
            token, img = banner_source(cfg, entry)
            title = creative_title(cfg, token, spec["name"])
            if _find("creative.create", {"group_id": gid, "title": title}):
                continue
            if not img.exists():
                raise FileNotFoundError(
                    f"banner for '{entry}' not found: {img} — check banners_dir/"
                    f"banner_sets and banner_pattern in campaign.yaml")
            crid = guard.create_creative(gid, title, click_url(cfg, token), str(img))
            out["creatives"].append({"id": crid, "title": title})

        # NB: for text ads `title` is the DISPLAYED headline, not an internal label
        for ad in cfg.get("text_ads", []):
            if _find("creative.create", {"group_id": gid, "title": ad["title"]}):
                continue
            crid = guard.create_text_creative(
                gid, ad["title"], click_url(cfg, ad["key"]),
                ad["description1"], ad["description2"], cfg["text_display_url"])
            out["creatives"].append({"id": crid, "key": ad["key"],
                                     "group": spec["name"], "type": "text"})

    if fund:
        already = sum(e["params"]["usd"] for e in ledger.entries("campaign.refill")
                      if e["params"].get("campaign_id") == cid)
        if already <= 0:
            out["funding"] = guard.refill_campaign(cid, camp["initial_funding"])
        else:
            out["funding"] = f"already funded ${already}, skipping"

    if activate:
        guard.activate_campaign(cid, True)
        for gid in out["groups"].values():
            guard.activate_group(gid, True)
        out["activated"] = True

    return out
