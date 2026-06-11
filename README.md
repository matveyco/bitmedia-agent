# bitmedia-agent

**An AI agent as your media buyer.** A guard-railed toolkit that lets an LLM
agent professionally buy, analyze, and optimize ad traffic on the
[Bitmedia.io](https://bitmedia.io) ad network — with hard, fail-closed spend
limits that make handing real money to an agent safe.

The agent does the judgment (reading reports, spotting bot traffic, deciding
what to blacklist and when to fund). The software does the enforcement: every
write goes through a **Guard** that refuses anything outside the limits a human
wrote down, and every action lands in an append-only **audit ledger**.

Built and battle-tested operating a real lead-generation campaign end-to-end —
launch, moderation, fraud defense, daily optimization — with an agent as the
only operator.

## How it works

```
Agent (Claude Code / Hermes, via the skill)
   │  judgment: what to do
   ▼
bitmedia-agent CLI ──── Guard (fail-closed limits: config/limits.yaml)
   │                       │
   │  every action         ├─ daily funding caps (drip-budget spend model)
   ▼                       ├─ bid ceilings, group-limit bounds
Bitmedia API               ├─ reserve-balance floor
                           └─ spend-velocity watchdog (auto-pause)
   ▲
GA4 Data API ── ground truth: did those clicks become engaged sessions and leads?
Ledger (data/ledger.jsonl) ── append-only audit of every mutation + decision
```

Key design points:

- **Drip-funding spend model.** Bitmedia's minimum group daily limit ($50,
  static bidding) usually exceeds a sensible test budget. The real control is
  the campaign balance: the Guard caps refills per UTC day, so money that was
  never moved can never be spent — three independent layers (refill caps, group
  limits, velocity watchdog) stand between the agent and overspend.
- **Per-publisher-site attribution with zero site changes.** The `{source}`
  macro rides inside `utm_content`, so GA4 answers "which publisher site
  produced this lead" — the evidence behind every blacklist decision.
- **Idempotent declarative launch.** `campaign.yaml` declares the campaign;
  `bitmedia-agent launch` builds exactly that, and re-running never duplicates
  (the ledger is the memory).
- **The agent cannot raise its own limits.** `config/limits.yaml` is human
  territory by contract; a `GUARD_REFUSED` answer is final.

## Quick start

```bash
git clone https://github.com/matveyco/bitmedia-agent.git
cd bitmedia-agent
python3 -m venv .venv && .venv/bin/pip install -e .

mkdir ~/my-campaign && cd ~/my-campaign
~/path/to/bitmedia-agent/.venv/bin/bitmedia-agent init
# fill .env (BITMEDIA_API_KEY, GA4_PROPERTY_ID), config/, drop banner PNGs in banners/
bitmedia-agent status            # verify API access
bitmedia-agent recommended-bid   # check the market for your geo BEFORE setting bids
bitmedia-agent launch            # build + fund + submit to moderation
bitmedia-agent moderation --watch  # auto-activate on approval
bitmedia-agent report            # the daily picture
```

Full setup (GA4 OAuth, lead-event discovery, scheduling):
[`skills/bitmedia-media-buyer/references/setup.md`](skills/bitmedia-media-buyer/references/setup.md)

## The agent skill

The [`skills/bitmedia-media-buyer/`](skills/bitmedia-media-buyer/) directory is
a portable [Agent Skill](https://agentskills.io): a SKILL.md operating manual
(daily decision loop, safety contract, escalation rules) plus a numeric
playbook the agent loads before judgment calls.

```bash
# Claude Code
cp -r skills/bitmedia-media-buyer ~/.claude/skills/
# Hermes Agent
cp -r skills/bitmedia-media-buyer ~/.hermes/skills/
```

Then: *"review my bitmedia campaign"* — or schedule it daily:

```cron
0 9 * * * cd /path/to/workspace && claude -p "Use the bitmedia-media-buyer skill: run the scheduled daily loop and write the decision summary." --allowedTools "Bash(bitmedia-agent:*),Read,Write,Grep" --max-turns 50 >> data/agent-runs/$(date +\%F).log 2>&1
```

## CLI overview

| | |
|---|---|
| `init`, `status`, `daily`, `report` | workspace scaffold; account/campaign state; daily data pull |
| `launch`, `fund`, `pause`, `resume` | idempotent build; guarded funding; delivery toggles |
| `bid`, `limit`, `blacklist`, `recommended-bid` | optimization levers (all Guard-checked) |
| `moderation [--watch]`, `guard-check` | creative approvals; velocity watchdog |
| `stats …`, `ga4 …`, `waitlist` | Bitmedia metrics; GA4 ground truth; optional KPI counter |

[`docs/bitmedia-api.md`](docs/bitmedia-api.md) is an unofficial reference for
the entire Bitmedia API, reverse-engineered from their Swagger spec and
verified against live behavior — useful well beyond this project.

## Disclaimer

Unofficial tooling, not affiliated with Bitmedia. It moves real money on your
ad account under limits you configure; review `config/limits.yaml` carefully
and start small. MIT licensed, no warranty.
