"""Compose the daily report: Bitmedia spend/delivery + GA4 + KPI, as markdown."""
import json
import os
from datetime import date, timedelta

from . import ga4, ledger, waitlist, workspace
from .bitmedia import campaigns, creatives, stats
from .bitmedia.client import Client
from .guard import Guard


def lead_event() -> str:
    workspace.load_env()
    return os.environ.get("GA4_LEAD_EVENT", "")


def _section(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except Exception as e:
        return {"error": str(e)}


def _md(obj) -> str:
    return "```json\n" + json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n```"


def daily(client: Client | None = None) -> str:
    c = client or Client()
    guard = Guard(c)
    today = date.today()
    frm = (today - timedelta(days=7)).isoformat()
    to = today.isoformat()

    parts = [f"# Daily report — {to}\n"]

    parts += ["## Account", _md({
        "balance": _section(stats.balance, c),
        "today_so_far": _section(stats.today, c),
        "velocity_check": _section(guard.velocity_check),
    })]

    for cid in set(ledger.our_campaign_ids()):
        info = _section(campaigns.info, c, cid)
        parts += [f"## Campaign {info.get('campaignName', cid)}", _md({
            "info": info,
            "daily_7d": _section(stats.daily, c, "campaign", cid, frm, to),
            "top_sources_7d": _section(stats.sources, c, "campaign", cid, frm, to, limit=25),
            "creatives": _section(creatives.list_, c, by="campaign", entity_id=cid),
        })]

    ga = {"traffic_by_source_7d": _section(ga4.traffic_by_source, 7),
          "bitmedia_breakdown_7d": _section(ga4.bitmedia_breakdown, 7)}
    event = lead_event()
    if event:
        ga["leads_7d"] = _section(ga4.leads_by_source, event, 7)
    else:
        ga["note"] = "GA4_LEAD_EVENT not set — run `bitmedia-agent ga4 events` to discover it"
    parts += ["## GA4", _md(ga)]

    parts += ["## KPI", _md(_section(waitlist.poll))]

    reports = workspace.reports_dir()
    reports.mkdir(parents=True, exist_ok=True)
    path = reports / f"{to}.md"
    path.write_text("\n\n".join(parts))
    return str(path)
