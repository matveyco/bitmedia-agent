# Media-buying playbook — thresholds and heuristics

Numbers here are working values learned from live operation (lead-gen, CPC,
tier-3 geo). Tune per campaign, but change them deliberately and record why in
the decisions file. Never "tune" `config/limits.yaml` — that is the human's file.

## The spend model (why the caps look odd)

Bitmedia requires group daily limits ≥ $50 with the static bid strategy — often
more than a whole test budget. So the **campaign balance is the real budget**:
money that was never moved into the campaign cannot be spent. The Guard caps
refills per UTC day (`daily_refill_cap`), making drip-funding the actual daily
spend ceiling. Group daily limits are only a secondary brake; the velocity
watchdog (`guard-check`) is the third layer.

Runway math: `campaign balance ÷ daily_spend_cap` = days left. Top up when
runway < 1 day — never more than the Guard allows, and only if quality holds.

## Source quality: blacklist criteria

Bitmedia bills per click (CPC); GA4 sessions are the ground truth for whether
those clicks were humans. Per publisher source id (carried in `utm_content`):

- **≥ 15 clicks and 0 GA4 engaged sessions** → blacklist (bot pattern).
- **Clicks-to-sessions ratio < 30%** with ≥ 20 clicks → blacklist (click
  inflation; some loss is normal — redirects, ad-blockers — but not 70%).
- **CTR > 3%** on a source with < 5% engagement rate → blacklist (display CTR
  above ~1% is already suspicious; 3%+ with dead sessions is fraud).
- **≥ $2 spend on one source with zero engaged sessions** → blacklist.
- Below $2 spend on a source: not enough evidence — leave it.
- Hourly click bursts (many clicks in one hour from one source, flat otherwise)
  → blacklist regardless of totals.

Always pass `--reason` with the evidence (e.g. "23 clicks, 1 session, 0 engaged").

## Creative rules

- Pause a creative after **≥ 2,000 impressions with CTR < 0.05%**.
- Judge size-vs-size only within the same group (mobile and desktop inventories
  differ structurally).
- Text ads: title and each description ≤ 35 characters (hard platform limit).
- Changing a creative's click URL resets its moderation approval — batch such
  changes and expect hours of downtime on that creative.

## Bid rules

- Stay inside the `recommended-bid` band; the Guard ceiling is absolute.
- Under-delivery (imps far below expectation, budget unspent): raise bid ~10-15%
  per day, one step per day, never past the band max or Guard ceiling.
- Budget exhausted early with poor quality: cut bid 10-15% or tighten targeting
  — don't pay premium for junk.
- A CPC bid where `bid > target_CPL × expected_LP_conversion` can never pay back
  — sanity-check against the funnel before raising.

## Quality benchmarks (engagement bar)

Compare `bitmedia` traffic in GA4 against the site's other paid channels. If
bitmedia sessions show < half the engagement rate of the best paid channel,
treat the network's traffic as suspect and tighten blacklisting. A healthy
display source typically shows: engaged-session rate ≥ 15%, average session
duration ≥ 15s, and some non-zero lead events over a week.

## Funding decision tree

1. Yesterday's spend produced sessions at acceptable quality? → fund up to cap.
2. Quality degraded but fixable (specific bad sources)? → blacklist first, fund
   reduced amount.
3. Quality systemically bad (most sources failing)? → do NOT fund; pause groups;
   escalate with evidence.

## Daily report reading order

balance → velocity → per-group spend/imps/clicks → per-source table → GA4
breakdown (sessions, engaged, duration per utm_content) → leads by source →
KPI counter delta. Verify geo: country stats must match the targeting — any
delivery outside target geo is a platform bug worth escalating.
