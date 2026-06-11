# Setup

## Install

```bash
git clone https://github.com/matveyco/bitmedia-agent.git
cd bitmedia-agent
python3 -m venv .venv && .venv/bin/pip install -e .
# put .venv/bin on PATH or symlink the binary:
ln -s "$PWD/.venv/bin/bitmedia-agent" /usr/local/bin/bitmedia-agent
```

## Workspace

A workspace is one operated ad account: configs, credentials, audit ledger,
reports. Keep exactly ONE workspace per account — the ledger inside it enforces
the daily funding caps and launch idempotency; duplicating it would double-spend.

```bash
mkdir my-campaign-workspace && cd my-campaign-workspace
bitmedia-agent init
```

Fill in:
- `.env` — `BITMEDIA_API_KEY` (Bitmedia dashboard → API), `GA4_PROPERTY_ID`
  (GA4 Admin → Property settings), `GA4_LEAD_EVENT` (after discovery, below).
- `config/limits.yaml` — your hard spend limits. The agent never edits this file.
- `config/campaign.yaml` — the declarative campaign plan. `utm_content` must keep
  the `{source}` macro: it carries the publisher site id into your analytics.
- Banner PNGs into the directory `banners_dir` points at, named per
  `banner_pattern` (e.g. `ad-banner-300x250.png`).

Optional: `NOTIFY_CMD` in `.env` — a shell command the agent pipes its daily
summary into (e.g. a curl to a Telegram bot).

## GA4 OAuth (one time, interactive)

1. Google Cloud console → create an OAuth client (type **Web application**),
   add `http://localhost:8765/` to its authorized redirect URIs.
2. **Set the OAuth consent screen to Production status** — in Testing status,
   refresh tokens expire after 7 days and scheduled runs silently degrade.
3. Save the client JSON as `credentials/ga4_client_secret.json`.
4. `bitmedia-agent ga4 auth` (or `--no-browser` to print the URL). Token refresh
   is automatic afterwards, including headless.
5. Discover the lead event: `bitmedia-agent ga4 events` → set `GA4_LEAD_EVENT`
   in `.env`.

## Agent runtimes

**Claude Code:** `cp -r skills/bitmedia-media-buyer ~/.claude/skills/`
**Hermes Agent:** `cp -r skills/bitmedia-media-buyer ~/.hermes/skills/`

## Scheduled daily run (cron example)

```cron
0 9 * * * cd /path/to/workspace && claude -p "Use the bitmedia-media-buyer skill: run the scheduled daily loop and write the decision summary." --allowedTools "Bash(bitmedia-agent:*),Read,Write,Grep" --max-turns 50 >> data/agent-runs/$(date +\%F).log 2>&1
```

The same prompt works with Hermes' headless runner. Failure behavior: a missing
`data/reports/<date>-decisions.md` for today means the run failed — check the
log. Re-running the same day is safe (reports are per-date; funding caps are
ledger-backed).
