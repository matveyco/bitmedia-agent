"""SAFETY LAYER — every mutating Bitmedia call goes through Guard, which validates
against config/limits.yaml, fails closed, and writes every action to the ledger.

The agent must never bypass Guard for writes, and must never edit limits.yaml
on its own — raising limits is a user decision.
"""
import yaml

from . import ledger, workspace
from .bitmedia import campaigns, creatives, groups, stats
from .bitmedia.client import Client
from .configcheck import validate_limits


class GuardRefusal(RuntimeError):
    """A hard limit would be violated. The action was NOT performed."""


class Guard:
    def __init__(self, client: Client):
        self.c = client
        self.limits = yaml.safe_load(workspace.limits_path().read_text())
        validate_limits(self.limits)

    # ---------- state helpers ----------

    def _today_refill_total(self) -> float:
        return sum(e["params"].get("usd", 0) for e in ledger.today_entries("campaign.refill"))

    def active_group_limits(self, exclude_group: str | None = None) -> dict[str, float]:
        """Daily limits of OUR currently-active groups, read live from the API."""
        out = {}
        for cid in set(ledger.our_campaign_ids()):
            info = campaigns.info(self.c, cid)
            for g in info.get("groupsStatus", []):
                gid = g.get("id")
                if gid == exclude_group:
                    continue
                if g.get("status") in ("Active", "Low balance", "Limit reached"):
                    lim = groups.get_limit(self.c, gid)
                    out[gid] = float(lim.get("amount", 0)) if lim.get("exists") else 0.0
        return out

    # ---------- guarded mutations ----------

    def create_campaign(self, name: str, currency: str = "USD") -> str:
        cid = campaigns.create(self.c, name, currency)
        ledger.append("campaign.create", {"name": name, "currency": currency}, cid)
        return cid

    def refill_campaign(self, campaign_id: str, usd: float) -> dict:
        lim = self.limits
        if usd <= 0:
            raise GuardRefusal("refill must be positive")
        if usd > lim["max_single_refill"]:
            raise GuardRefusal(f"refill ${usd} > max_single_refill ${lim['max_single_refill']}")
        today_total = self._today_refill_total()
        if today_total + usd > lim["daily_refill_cap"]:
            raise GuardRefusal(f"refill ${usd} + today's ${today_total} "
                               f"> daily_refill_cap ${lim['daily_refill_cap']}")
        bal = stats.balance(self.c)
        if bal["usd"] - usd < lim["reserve_balance"]:
            raise GuardRefusal(
                f"refill would leave user balance ${bal['usd'] - usd} "
                f"< reserve ${lim['reserve_balance']}"
                " (unlocking the reserve is a user decision in config/limits.yaml)")
        res = campaigns.refill_usd(self.c, campaign_id, usd)
        ledger.append("campaign.refill", {"campaign_id": campaign_id, "usd": usd}, res)
        return {"refilled": usd, "user_balance_after": bal["usd"] - usd}

    def create_group(self, name: str, campaign_id: str, *, group_type: str,
                     bid: float, daily_limit: float, bid_strategy: str = "static") -> str:
        self._check_bid(bid, group_type)
        self._check_group_limit(daily_limit)
        gid = groups.create(self.c, name, campaign_id, group_type=group_type,
                            bid_strategy=bid_strategy, bid=bid, daily_limit=daily_limit)
        ledger.append("group.create", {"name": name, "campaign_id": campaign_id,
                                       "type": group_type, "bid": bid,
                                       "daily_limit": daily_limit}, gid)
        return gid

    def set_bid(self, group_id: str, bid: float, group_type: str = "native_cpc"):
        self._check_bid(bid, group_type)
        res = groups.set_bid(self.c, group_id, bid, group_type)
        ledger.append("group.bid", {"group_id": group_id, "bid": bid}, res)
        return res

    def set_group_limit(self, group_id: str, daily_limit: float):
        self._check_group_limit(daily_limit)
        res = groups.set_limit(self.c, group_id, daily_limit, enabled=True)
        ledger.append("group.limit", {"group_id": group_id, "daily_limit": daily_limit}, res)
        return res

    def set_targeting(self, group_id: str, **kwargs):
        res = groups.set_targeting(self.c, group_id, **kwargs)
        logged = {k: v for k, v in kwargs.items()
                  if k in ("countries", "vpn_traffic", "frequency")}
        ledger.append("group.targeting", {"group_id": group_id, **logged}, "ok")
        return res

    def activate_group(self, group_id: str, is_active: bool = True):
        if is_active:
            lim = groups.get_limit(self.c, group_id)
            if not lim.get("exists"):
                raise GuardRefusal(
                    f"group {group_id} has no daily limit set — refusing to activate")
        res = groups.activate(self.c, group_id, is_active)
        ledger.append("group.activate", {"group_id": group_id, "is_active": is_active}, res)
        return res

    def activate_campaign(self, campaign_id: str, is_active: bool = True):
        res = campaigns.activate(self.c, campaign_id, is_active)
        ledger.append("campaign.activate",
                      {"campaign_id": campaign_id, "is_active": is_active}, res)
        return res

    def create_creative(self, group_id: str, title: str, click_url: str,
                        image_path: str) -> str:
        crid = creatives.create_image(self.c, group_id, title, click_url)
        up = creatives.upload_images(self.c, crid, [image_path])
        ledger.append("creative.create", {"group_id": group_id, "title": title,
                                          "click_url": click_url, "image": image_path},
                      {"creative_id": crid, "upload": up})
        return crid

    def create_text_creative(self, group_id: str, title: str, click_url: str,
                             description1: str, description2: str, display_url: str) -> str:
        crid = creatives.create_text(self.c, group_id, title, click_url,
                                     description1, description2, display_url)
        ledger.append("creative.create", {"group_id": group_id, "title": title,
                                          "click_url": click_url, "type": "text",
                                          "description1": description1,
                                          "description2": description2},
                      {"creative_id": crid})
        return crid

    def activate_creative(self, creative_id: str, is_active: bool = True):
        res = creatives.activate(self.c, creative_id, is_active)
        ledger.append("creative.activate",
                      {"creative_id": creative_id, "is_active": is_active}, res)
        return res

    def blacklist_sources(self, group_id: str, source_ids: list[str], reason: str = ""):
        res = groups.blacklist(self.c, group_id, source_ids)
        ledger.append("group.blacklist", {"group_id": group_id, "source_ids": source_ids},
                      "ok", note=reason)
        return res

    # ---------- checks ----------

    def _check_bid(self, bid: float, group_type: str):
        ceiling = (self.limits["max_cpc_bid"] if group_type == "native_cpc"
                   else self.limits["max_cpm_bid"])
        if bid > ceiling:
            raise GuardRefusal(f"bid ${bid} > ceiling ${ceiling} for {group_type}")

    def _check_group_limit(self, daily_limit: float):
        """Platform forces group limits >= $50; the real $30/day control is the
        campaign-balance drip (refill caps). Bound the secondary brake anyway."""
        lo, hi = self.limits["group_daily_limit_min"], self.limits["group_daily_limit_max"]
        if not lo <= daily_limit <= hi:
            raise GuardRefusal(f"group daily limit ${daily_limit} outside [{lo}, {hi}]")

    # ---------- anomaly watchdog ----------

    def velocity_check(self) -> dict:
        """Auto-pause if today's spend exceeds factor * daily_spend_cap."""
        spent = float(stats.today(self.c).get("spends", 0) or 0)
        threshold = self.limits["daily_spend_cap"] * self.limits["velocity_pause_factor"]
        tripped = spent > threshold
        if tripped:
            active = self.active_group_limits()
            for gid in active:
                groups.activate(self.c, gid, False)
            ledger.append("guard.velocity_pause",
                          {"spent_today": spent, "threshold": threshold,
                           "paused_groups": list(active)}, "PAUSED ALL GROUPS")
        return {"spent_today": spent, "daily_spend_cap": self.limits["daily_spend_cap"],
                "threshold": threshold, "tripped": tripped}
