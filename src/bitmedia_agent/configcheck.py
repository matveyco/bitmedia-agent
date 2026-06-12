"""Light config validation — fail fast with a clear message, no schema library."""

MAX_TITLE_LEN = 35  # platform limit for creative titles (image and text alike)

DEFAULT_TITLE_PATTERN = "{campaign}-{size}-{group}"


def creative_token(entry: str) -> str:
    """'300x250' -> '300x250'; 'ar:300x250' -> 'ar-300x250'."""
    return entry.replace(":", "-", 1)


def creative_title(cfg: dict, token: str, group: str) -> str:
    pattern = cfg.get("creative_title_pattern", DEFAULT_TITLE_PATTERN)
    return (pattern.replace("{campaign}", cfg["campaign"]["name"])
                   .replace("{size}", token).replace("{group}", group))


LIMIT_KEYS = [
    "daily_spend_cap", "daily_refill_cap", "max_single_refill",
    "group_daily_limit_min", "group_daily_limit_max",
    "max_cpc_bid", "max_cpm_bid", "reserve_balance", "velocity_pause_factor",
]


def validate_limits(cfg: dict) -> None:
    missing = [k for k in LIMIT_KEYS if k not in cfg]
    if missing:
        raise ValueError(f"limits.yaml missing keys: {missing}")
    bad = [k for k in LIMIT_KEYS if not isinstance(cfg[k], (int, float)) or cfg[k] <= 0]
    if bad:
        raise ValueError(f"limits.yaml keys must be positive numbers: {bad}")
    if cfg["max_single_refill"] > cfg["daily_refill_cap"]:
        raise ValueError("max_single_refill cannot exceed daily_refill_cap")
    if cfg["group_daily_limit_min"] > cfg["group_daily_limit_max"]:
        raise ValueError("group_daily_limit_min cannot exceed group_daily_limit_max")


def validate_campaign(cfg: dict) -> None:
    for path in ("campaign", "landing", "defaults", "groups"):
        if path not in cfg:
            raise ValueError(f"campaign.yaml missing section: {path}")
    if not cfg["campaign"].get("name"):
        raise ValueError("campaign.name is required")
    land = cfg["landing"]
    if not land.get("base_url"):
        raise ValueError("landing.base_url is required")
    if "{source}" not in land.get("utm_content", ""):
        raise ValueError("landing.utm_content must contain the {source} macro "
                         "(per-publisher-site attribution)")
    if not cfg["defaults"].get("countries"):
        raise ValueError("defaults.countries is required (ISO-2 codes)")
    if not cfg["groups"]:
        raise ValueError("at least one group is required")
    sets = cfg.get("banner_sets") or {}
    for key, spec in sets.items():
        if not isinstance(spec, dict) or "dir" not in spec:
            raise ValueError(f"banner_sets.{key} must define 'dir'")
    for g in cfg["groups"]:
        for k in ("name", "bid", "daily_limit", "mobile_os", "desktop_os", "creatives"):
            if k not in g:
                raise ValueError(f"group {g.get('name', '?')} missing key: {k}")
        for entry in g["creatives"]:
            if ":" in entry and entry.split(":", 1)[0] not in sets:
                raise ValueError(
                    f"group {g['name']}: creative '{entry}' references undefined "
                    f"banner set '{entry.split(':', 1)[0]}'")
            title = creative_title(cfg, creative_token(entry), g["name"])
            if len(title) > MAX_TITLE_LEN:
                raise ValueError(
                    f"creative title '{title}' is {len(title)} chars — platform max is "
                    f"{MAX_TITLE_LEN}. Use shorter banner-set keys or group names.")
    for ad in cfg.get("text_ads") or []:
        for field in ("title", "description1", "description2"):
            if len(ad.get(field, "")) > MAX_TITLE_LEN:
                raise ValueError(
                    f"text ad {ad.get('key')}: {field} exceeds {MAX_TITLE_LEN} chars "
                    "(platform limit)")
