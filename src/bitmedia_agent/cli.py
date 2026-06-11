"""Media-buyer CLI for Bitmedia. All write operations pass through the Guard."""
import json
import shutil
import time
from datetime import date, timedelta
from importlib import resources

import typer

from . import __version__, ledger, workspace
from . import ga4 as ga4mod
from . import waitlist as wl
from .bitmedia import campaigns, creatives, groups
from .bitmedia import stats as st
from .bitmedia.client import Client
from .guard import Guard, GuardRefusal

app = typer.Typer(no_args_is_help=True, help=__doc__)
stats_app = typer.Typer(no_args_is_help=True, help="Read-only statistics.")
ga4_app = typer.Typer(no_args_is_help=True, help="GA4 analytics (auth + queries).")
app.add_typer(stats_app, name="stats")
app.add_typer(ga4_app, name="ga4")


def out(obj):
    typer.echo(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def _dates(days: int):
    today = date.today()
    return (today - timedelta(days=days)).isoformat(), today.isoformat()


@app.command()
def version():
    typer.echo(__version__)


@app.command()
def init():
    """Scaffold a workspace (config templates, data/, credentials/) in BITMEDIA_WORKSPACE or cwd."""
    root = workspace.root()
    created = []
    for sub in ("config", "data/reports", "credentials"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    tdir = resources.files("bitmedia_agent") / "templates"
    for name in ("limits.yaml", "campaign.yaml"):
        dest = root / "config" / name
        if dest.exists():
            created.append(f"{dest} exists — left untouched")
        else:
            shutil.copyfile(str(tdir / name), dest)
            created.append(f"created {dest}")
    env = root / ".env"
    if not env.exists():
        env.write_text("BITMEDIA_API_KEY=\nGA4_PROPERTY_ID=\nGA4_LEAD_EVENT=\n")
        created.append(f"created {env} — fill in your keys")
    gi = root / ".gitignore"
    if not gi.exists():
        gi.write_text("credentials/\n.env\ndata/\n")
        created.append(f"created {gi}")
    out({"workspace": str(root), "actions": created})


@app.command()
def status():
    """Balance, today's spend, our campaigns with group/creative states."""
    c = Client()
    res = {"balance": st.balance(c), "today": st.today(c)}
    res["campaigns"] = {cid: campaigns.info(c, cid) for cid in set(ledger.our_campaign_ids())}
    out(res)


@app.command()
def daily():
    """Deterministic daily pull: guard-check -> full report -> KPI. Emits JSON for the agent."""
    from .report import daily as daily_report
    g = Guard(Client())
    velocity = g.velocity_check()
    warnings = []
    if velocity["tripped"]:
        warnings.append("VELOCITY TRIPPED — groups paused; human review required")
    report_path = daily_report()
    out({"report_path": report_path, "velocity": velocity, "warnings": warnings})


@app.command()
def launch(no_fund: bool = False, no_activate: bool = False):
    """Build the campaign declared in config/campaign.yaml (idempotent)."""
    from .launch import launch as do_launch
    try:
        out(do_launch(fund=not no_fund, activate=not no_activate))
    except GuardRefusal as e:
        out({"GUARD_REFUSED": str(e)})
        raise typer.Exit(2)


@app.command()
def fund(campaign_id: str, usd: float):
    try:
        out(Guard(Client()).refill_campaign(campaign_id, usd))
    except GuardRefusal as e:
        out({"GUARD_REFUSED": str(e)})
        raise typer.Exit(2)


@app.command()
def pause(campaign: str = "", group: str = "", creative: str = ""):
    _toggle(campaign, group, creative, False)


@app.command()
def resume(campaign: str = "", group: str = "", creative: str = ""):
    _toggle(campaign, group, creative, True)


def _toggle(campaign_id: str, group_id: str, creative_id: str, active: bool):
    g = Guard(Client())
    try:
        if campaign_id:
            out(g.activate_campaign(campaign_id, active))
        elif group_id:
            out(g.activate_group(group_id, active))
        elif creative_id:
            out(g.activate_creative(creative_id, active))
        else:
            out({"error": "pass --campaign, --group or --creative"})
    except GuardRefusal as e:
        out({"GUARD_REFUSED": str(e)})
        raise typer.Exit(2)


@app.command()
def bid(group_id: str, value: float, group_type: str = "native_cpc"):
    try:
        out(Guard(Client()).set_bid(group_id, value, group_type))
    except GuardRefusal as e:
        out({"GUARD_REFUSED": str(e)})
        raise typer.Exit(2)


@app.command("limit")
def limit_(group_id: str, daily_limit: float):
    try:
        out(Guard(Client()).set_group_limit(group_id, daily_limit))
    except GuardRefusal as e:
        out({"GUARD_REFUSED": str(e)})
        raise typer.Exit(2)


@app.command()
def blacklist(group_id: str, source_ids: list[str], reason: str = ""):
    out(Guard(Client()).blacklist_sources(group_id, source_ids, reason))


@app.command("recommended-bid")
def recommended_bid(devices: str = "mobile", countries: str = "",
                    group_type: str = "native_cpc"):
    """Market bid band. Default countries come from campaign.yaml targeting."""
    if not countries:
        import yaml
        cfg = yaml.safe_load(workspace.campaign_path().read_text())
        countries = ",".join(cfg["defaults"]["countries"])
    out(groups.recommended_bid(Client(), devices=devices, countries=countries,
                               group_type=group_type))


def _moderation_rows(c: Client) -> list[dict]:
    rows = []
    for cid in set(ledger.our_campaign_ids()):
        data = creatives.list_(c, by="campaign", entity_id=cid)
        for item in (data.get("items") if isinstance(data, dict) else data) or []:
            s = item.get("status", {})
            rows.append({"id": item.get("_id"), "title": item.get("title"),
                         "active": s.get("active"), "approved": s.get("approved"),
                         "denyReason": s.get("denyReason")})
    return rows


@app.command()
def moderation(watch: bool = False, interval: int = 600, max_hours: int = 24):
    """Approval status of our creatives. --watch polls and auto-activates on first approval."""
    c = Client()
    if not watch:
        out(_moderation_rows(c))
        return
    guard = Guard(c)
    deadline = time.time() + max_hours * 3600
    while time.time() < deadline:
        rows = _moderation_rows(c)
        approved = [r for r in rows if r["approved"] is True]
        denied = [r for r in rows if r["approved"] is False]
        typer.echo(f"approved={len(approved)} denied={len(denied)} "
                   f"pending={len(rows) - len(approved) - len(denied)}")
        if denied:
            out(denied)
        if approved:
            for cid in set(ledger.our_campaign_ids()):
                guard.activate_campaign(cid, True)
            for gid in set(ledger.our_group_ids()):
                guard.activate_group(gid, True)
            typer.echo("ACTIVATED campaign + groups.")
            return
        time.sleep(interval)
    typer.echo(f"timed out after {max_hours}h without approvals")
    raise typer.Exit(1)


@app.command("guard-check")
def guard_check():
    """Run the spend-velocity watchdog (auto-pauses on anomaly)."""
    out(Guard(Client()).velocity_check())


@app.command()
def waitlist():
    out(wl.poll())


@app.command()
def report():
    """Compose today's full report -> data/reports/YYYY-MM-DD.md."""
    from .report import daily
    typer.echo(daily())


@stats_app.command("today")
def stats_today():
    out(st.today(Client()))


@stats_app.command("daily")
def stats_daily(entity: str, entity_id: str, days: int = 7, group_by: str = "1d"):
    frm, to = _dates(days)
    out(st.daily(Client(), entity, entity_id, frm, to, group_by))


@stats_app.command("sources")
def stats_sources(entity: str, entity_id: str, days: int = 3):
    frm, to = _dates(days)
    out(st.sources(Client(), entity, entity_id, frm, to))


@stats_app.command("countries")
def stats_countries(days: int = 7):
    frm, to = _dates(days)
    out(st.countries(Client(), frm, to))


@stats_app.command("creatives")
def stats_creatives(days: int = 7):
    frm, to = _dates(days)
    out(st.general(Client(), "creative", frm, to))


@ga4_app.command("auth")
def ga4_auth(no_browser: bool = False):
    """One-time OAuth consent. --no-browser prints the URL instead of opening one."""
    typer.echo(ga4mod.auth(open_browser=not no_browser))


@ga4_app.command("events")
def ga4_events(days: int = 7):
    out(ga4mod.event_inventory(days))


@ga4_app.command("traffic")
def ga4_traffic(days: int = 7):
    out(ga4mod.traffic_by_source(days))


@ga4_app.command("breakdown")
def ga4_breakdown(days: int = 7):
    out(ga4mod.bitmedia_breakdown(days))


@ga4_app.command("leads")
def ga4_leads(event: str, days: int = 7):
    out(ga4mod.leads_by_source(event, days))


if __name__ == "__main__":
    app()
