"""Ad group endpoints: bid, daily limit, targeting, site white/blacklists."""
from .client import Client

# displayDesktopOs / displayMobileOs must each contain exactly these 4 names
DESKTOP_OS = ["linux", "windows", "macos", "others"]
MOBILE_OS = ["android", "winmobile", "ios", "others"]


def create(c: Client, name: str, campaign_id: str, *, group_type: str = "native_cpc",
           bid_strategy: str = "static", bid: float, daily_limit: float) -> str:
    return c.post("/api/groups/create", {
        "name": name,
        "campaignId": campaign_id,
        "type": group_type,
        "bidStrategy": bid_strategy,
        "bid": bid,
        "groupDailyLimit": daily_limit,
    })


def activate(c: Client, group_id: str, is_active: bool):
    return c.post("/api/groups/activate-group", {"id": group_id, "isActive": is_active})


def get_bid(c: Client, group_id: str):
    return c.get("/api/groups/group-bid", id=group_id)


def set_bid(c: Client, group_id: str, new_bid: float, group_type: str | None = None):
    body = {"id": group_id, "newBid": new_bid}
    if group_type:
        body["type"] = group_type
    return c.post("/api/groups/group-bid", body)


def recommended_bid(c: Client, *, devices: str, countries: str = "",
                    group_type: str = "native_cpc", currency: str = "USD"):
    """devices: 'mobile', 'desktop' or comma list like 'mobile_android,mobile_ios'."""
    return c.get("/api/groups/recommended-bid", devices=devices, countries=countries,
                 type=group_type, currency=currency)


def get_limit(c: Client, group_id: str):
    return c.get("/api/groups/group-limit", id=group_id)


def set_limit(c: Client, group_id: str, daily_limit: float, enabled: bool = True):
    return c.post("/api/groups/group-limit", {
        "id": group_id, "dailyLimitStatus": enabled, "groupDailyLimit": daily_limit,
    })


def _os_array(names: list[str], enabled: dict) -> list[dict]:
    return [{"name": n, "value": bool(enabled.get(n, False))} for n in names]


def set_targeting(c: Client, group_id: str, *, countries: list[str],
                  mobile_os: dict, desktop_os: dict,
                  vpn_traffic: str = "excluded", languages: list[str] | None = None,
                  frequency: dict | None = None, ad_rerun: int = 72,
                  display_time: dict | None = None, pacing_split: bool = False):
    """Master targeting call. frequency = {'enabled': bool, 'value': int, 'time': hours}."""
    freq = frequency or {}
    body = {
        "id": group_id,
        "adRerun": ad_rerun,
        "displayDesktop": any(desktop_os.values()),
        "displayMobile": any(mobile_os.values()),
        "displayDesktopOs": _os_array(DESKTOP_OS, desktop_os),
        "displayMobileOs": _os_array(MOBILE_OS, mobile_os),
        "displayTimeRange": display_time or {"from": 0, "to": 24},
        "budgetShouldBeSplit": pacing_split,
        "frequencyCapping": bool(freq.get("enabled", False)),
        "frequencyTarget": "advertisement",
        "frequencyTime": int(freq.get("time", 24)),
        "frequencyValue": int(freq.get("value", 0)),
        "language": languages or [],
        "preferredCountries": countries,
        "excludedCountries": [],
        "whitelistedRegions": [],
        "blacklistedRegions": [],
        "whitelistedAdvertBlocks": [],
        "blacklistedAdvertBlocks": [],
        "whitelistedAudiences": [],
        "blacklistedAudiences": [],
        "trafficType": vpn_traffic,
        "displayType": {"allowSticky": True, "allowRegular": True},
    }
    return c.post("/api/groups/set-group-targeting", body)


def sources_list(c: Client, group_id: str):
    return c.get("/api/groups/sources-white-black-list", id=group_id)


def blacklist(c: Client, group_id: str, source_ids: list[str], action: str = "add"):
    return c.post(f"/api/groups/sources-white-black-list/{action}", {
        "id": group_id, "list": "blocked_sources", "sourceIds": source_ids,
    })


def group_info(c: Client, group_id: str):
    return c.get("/api/groups/group-info", id=group_id)
