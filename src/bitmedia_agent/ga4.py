"""GA4 Data API: OAuth bootstrap (one-time) + lead/traffic queries."""
import json
import os

from . import workspace

SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
OAUTH_PORT = 8765


def client_secret_path():
    return workspace.credentials_dir() / "ga4_client_secret.json"


def token_path():
    return workspace.credentials_dir() / "ga4_token.json"


def property_id() -> str:
    workspace.load_env()
    prop = os.environ.get("GA4_PROPERTY_ID")
    if not prop:
        raise RuntimeError("GA4_PROPERTY_ID is not set (workspace .env)")
    return prop


def auth(open_browser: bool = True) -> str:
    """One-time interactive OAuth flow; stores a refresh token.

    The OAuth client is a 'web' type: http://localhost:8765/ must be listed in its
    authorized redirect URIs (Google Cloud console -> Credentials). The consent
    screen must be in Production status or refresh tokens expire after 7 days.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow
    secret = client_secret_path()
    if not secret.exists():
        raise RuntimeError(f"missing OAuth client secret: {secret}")
    flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
    creds = flow.run_local_server(port=OAUTH_PORT, open_browser=open_browser,
                                  prompt="consent")
    token_path().write_text(creds.to_json())
    return f"token saved to {token_path()}"


def _credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    tp = token_path()
    if not tp.exists():
        raise RuntimeError("GA4 not authorized yet — run: bitmedia-agent ga4 auth")
    creds = Credentials.from_authorized_user_info(json.loads(tp.read_text()), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        tp.write_text(creds.to_json())
    return creds


def _client():
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    return BetaAnalyticsDataClient(credentials=_credentials())


def run_report(dimensions: list[str], metrics: list[str], days: int = 7,
               dim_filter=None, limit: int = 250) -> list[dict]:
    from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
    req = RunReportRequest(
        property=f"properties/{property_id()}",
        dimensions=[Dimension(name=d) for d in dimensions],
        metrics=[Metric(name=m) for m in metrics],
        date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
        dimension_filter=dim_filter,
        limit=limit,
    )
    resp = _client().run_report(req)
    rows = []
    for r in resp.rows:
        row = {d: v.value for d, v in zip(dimensions, r.dimension_values)}
        row.update({m: v.value for m, v in zip(metrics, r.metric_values)})
        rows.append(row)
    return rows


def event_inventory(days: int = 7) -> list[dict]:
    """All event names with counts — used to discover the lead/conversion event."""
    return run_report(["eventName"], ["eventCount"], days=days)


def traffic_by_source(days: int = 7) -> list[dict]:
    return run_report(
        ["sessionSource", "sessionMedium", "sessionCampaignName"],
        ["sessions", "engagedSessions", "averageSessionDuration"], days=days)


def bitmedia_breakdown(days: int = 7) -> list[dict]:
    """Per-utm_content breakdown of bitmedia traffic (content carries the {source} id)."""
    from google.analytics.data_v1beta.types import Filter, FilterExpression
    f = FilterExpression(filter=Filter(
        field_name="sessionSource",
        string_filter=Filter.StringFilter(value="bitmedia")))
    return run_report(
        ["sessionManualAdContent", "countryId"],
        ["sessions", "engagedSessions", "averageSessionDuration"],
        days=days, dim_filter=f)


def leads_by_source(event_name: str, days: int = 7) -> list[dict]:
    from google.analytics.data_v1beta.types import Filter, FilterExpression
    f = FilterExpression(filter=Filter(
        field_name="eventName",
        string_filter=Filter.StringFilter(value=event_name)))
    return run_report(
        ["sessionSource", "sessionMedium", "sessionManualAdContent", "countryId"],
        ["eventCount"], days=days, dim_filter=f)
