"""Append-only audit ledger: every mutation and decision, with params and result.

Doubles as the data source for guard state (e.g. today's refill total) and as the
raw material for the eventual case study.
"""
import json
from datetime import datetime, timezone

from . import workspace


def append(action: str, params: dict, result, note: str = "") -> dict:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "action": action,
        "params": params,
        "result": result,
        "note": note,
    }
    path = workspace.ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    return entry


def entries(action: str | None = None) -> list[dict]:
    path = workspace.ledger_path()
    if not path.exists():
        return []
    out = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            if action is None or e["action"] == action:
                out.append(e)
    return out


def today_entries(action: str) -> list[dict]:
    today = datetime.now(timezone.utc).date().isoformat()
    return [e for e in entries(action) if e["ts"].startswith(today)]


def our_campaign_ids() -> list[str]:
    """Campaigns created by this tool (the only ones the bot manages)."""
    return [e["result"] for e in entries("campaign.create") if isinstance(e["result"], str)]


def our_group_ids() -> list[str]:
    return [e["result"] for e in entries("group.create") if isinstance(e["result"], str)]
