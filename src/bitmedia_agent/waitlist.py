"""Poll an optional public KPI counter (e.g. a waitlist count endpoint).

Configured via campaign.yaml -> kpi.waitlist_count_url; coarse signal (includes
organic traffic), tracked for trend only.
"""
import json
from datetime import datetime, timezone

import httpx
import yaml

from . import workspace


def configured_url() -> str | None:
    path = workspace.campaign_path()
    if not path.exists():
        return None
    cfg = yaml.safe_load(path.read_text()) or {}
    return (cfg.get("kpi") or {}).get("waitlist_count_url")


def poll(url: str | None = None) -> dict:
    url = url or configured_url()
    if not url:
        return {"disabled": True, "note": "kpi.waitlist_count_url not set in campaign.yaml"}
    count = httpx.get(url, timeout=30).json()["count"]
    prev = last()
    entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "count": count}
    path = workspace.waitlist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    entry["delta"] = count - prev["count"] if prev else None
    return entry


def last() -> dict | None:
    path = workspace.waitlist_path()
    if not path.exists():
        return None
    lines = path.read_text().strip().splitlines()
    return json.loads(lines[-1]) if lines else None
