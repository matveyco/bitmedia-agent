"""Read-only statistics endpoints."""
from .client import Client


def balance(c: Client):
    return c.get("/api/user/balance")


def today(c: Client, currency: str = "USD"):
    return c.get("/api/owner-statistics/today-so-far-statistics", currency=currency)


def daily(c: Client, entity: str, entity_id: str, from_date: str, to_date: str,
          group_by: str = "1d"):
    """entity: campaign | group | creative. Dates YYYY-MM-DD. 1h <= 7 days back, 1d <= 90."""
    return c.get(f"/api/owner-statistics/detailed-daily-statistics/{entity}",
                 id=entity_id, groupBy=group_by, fromDate=from_date, toDate=to_date)


def daily_by_country(c: Client, entity: str, entity_id: str, from_date: str, to_date: str,
                     group_by: str = "1d", country: str | None = None):
    return c.get(f"/api/owner-statistics/detailed-daily-country-statistics/{entity}",
                 id=entity_id, groupBy=group_by, fromDate=from_date, toDate=to_date,
                 country=country)


def sources(c: Client, entity: str, entity_id: str, from_date: str, to_date: str,
            skip: int = 0, limit: int = 100):
    """Per-publisher-site stats — the main optimization lever. entity: campaign | group."""
    return c.get(f"/api/owner-statistics/sources-statistics/{entity}",
                 id=entity_id, fromDate=from_date, toDate=to_date, skip=skip, limit=limit)


def general(c: Client, statistics_of: str, from_date: str, to_date: str,
            skip: int = 0, limit: int = 100):
    """statistics_of: campaign | group | creative — aggregated table with deltas."""
    return c.get("/api/owner-statistics/general-statistics-advert",
                 statisticsOf=statistics_of, fromDate=from_date, toDate=to_date,
                 skip=skip, limit=limit)


def countries(c: Client, from_date: str, to_date: str, skip: int = 0, limit: int = 100):
    return c.get("/api/owner-statistics/general-statistics-countries",
                 fromDate=from_date, toDate=to_date, skip=skip, limit=limit)
