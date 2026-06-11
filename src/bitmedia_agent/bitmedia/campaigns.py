"""Campaign endpoints. A campaign holds a name + balance; the balance IS its budget."""
from .client import Client


def create(c: Client, name: str, currency: str = "USD") -> str:
    return c.request("POST", "/api/campaigns/create", params={"currency": currency},
                     json={"name": name, "isInternal": False})


def list_(c: Client, skip: int = 0, limit: int = 100, archived: int = 0, name: str | None = None):
    return c.get("/api/campaigns/list", skip=skip, limit=limit, archived=archived, name=name)


def info(c: Client, campaign_id: str):
    return c.get("/api/campaigns/campaign-info", id=campaign_id)


def activate(c: Client, campaign_id: str, is_active: bool):
    return c.post("/api/campaigns/activate-campaign", {"id": campaign_id, "isActive": is_active})


def refill_usd(c: Client, campaign_id: str, usd: float):
    """Moves money: user balance -> campaign balance."""
    return c.post("/api/campaigns/usd-refill-campaign", {"id": campaign_id, "usdAmount": usd})


def refund_to_main(c: Client, campaign_id: str, usd: float):
    """Moves money back: campaign balance -> user balance."""
    return c.post("/api/campaigns/main-refill-campaign", {"campaignId": campaign_id, "amount": usd})


def balances(c: Client, currency: str = "USD"):
    return c.get("/api/campaigns/campaigns-balances", currency=currency)
