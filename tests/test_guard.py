"""Characterization tests for the Guard refusal matrix — semantics are frozen.

Any behavior change here is a regression in the safety layer, not an improvement.
"""
import pytest

from bitmedia_agent import ledger
from bitmedia_agent.guard import Guard, GuardRefusal
from tests.conftest import FakeClient

BALANCE_OK = {("GET", "/api/user/balance"): {"usd": 1000, "balanceCampaigns": 0}}


def make_guard(routes=None):
    return Guard(FakeClient(routes or {}))


# ---------- refill ----------

def test_refill_rejects_nonpositive(ws):
    with pytest.raises(GuardRefusal, match="positive"):
        make_guard().refill_campaign("c1", 0)
    with pytest.raises(GuardRefusal, match="positive"):
        make_guard().refill_campaign("c1", -5)


def test_refill_rejects_over_single_cap(ws):
    with pytest.raises(GuardRefusal, match="max_single_refill"):
        make_guard().refill_campaign("c1", 31)


def test_refill_rejects_over_daily_cap(ws):
    ledger.append("campaign.refill", {"campaign_id": "c1", "usd": 20}, None)
    with pytest.raises(GuardRefusal, match="daily_refill_cap"):
        make_guard(BALANCE_OK).refill_campaign("c1", 15)


def test_refill_rejects_reserve_breach(ws):
    g = make_guard({("GET", "/api/user/balance"): {"usd": 410}})
    with pytest.raises(GuardRefusal, match="reserve"):
        g.refill_campaign("c1", 20)


def test_refill_happy_path_calls_api_and_ledgers(ws):
    g = make_guard({**BALANCE_OK, ("POST", "/api/campaigns/usd-refill-campaign"): None})
    res = g.refill_campaign("c1", 30)
    assert res["refilled"] == 30
    assert g.c.called("POST", "/api/campaigns/usd-refill-campaign")
    refills = ledger.entries("campaign.refill")
    assert len(refills) == 1 and refills[0]["params"]["usd"] == 30


def test_refill_daily_cap_counts_only_today(ws):
    # an old entry must not count toward today's cap
    import json

    from bitmedia_agent import workspace
    old = {"ts": "2020-01-01T00:00:00+00:00", "action": "campaign.refill",
           "params": {"campaign_id": "c1", "usd": 30}, "result": None, "note": ""}
    workspace.ledger_path().parent.mkdir(parents=True, exist_ok=True)
    workspace.ledger_path().write_text(json.dumps(old) + "\n")
    g = make_guard({**BALANCE_OK, ("POST", "/api/campaigns/usd-refill-campaign"): None})
    assert g.refill_campaign("c1", 30)["refilled"] == 30


# ---------- bids ----------

def test_bid_ceiling_cpc(ws):
    with pytest.raises(GuardRefusal, match="ceiling"):
        make_guard().set_bid("g1", 0.51, "native_cpc")


def test_bid_ceiling_cpm(ws):
    with pytest.raises(GuardRefusal, match="ceiling"):
        make_guard().set_bid("g1", 1.01, "native_cpm")


def test_bid_at_ceiling_allowed(ws):
    g = make_guard({("POST", "/api/groups/group-bid"): None})
    g.set_bid("g1", 0.50, "native_cpc")
    assert g.c.called("POST", "/api/groups/group-bid")
    assert ledger.entries("group.bid")


# ---------- group limits ----------

@pytest.mark.parametrize("bad", [49, 61, 0])
def test_group_limit_bounds(ws, bad):
    with pytest.raises(GuardRefusal, match="outside"):
        make_guard().set_group_limit("g1", bad)


def test_group_limit_in_bounds(ws):
    g = make_guard({("POST", "/api/groups/group-limit"): None})
    g.set_group_limit("g1", 50)
    assert g.c.called("POST", "/api/groups/group-limit")


# ---------- activation ----------

def test_activate_group_requires_limit(ws):
    g = make_guard({("GET", "/api/groups/group-limit"): {"exists": False}})
    with pytest.raises(GuardRefusal, match="no daily limit"):
        g.activate_group("g1", True)


def test_activate_group_with_limit(ws):
    g = make_guard({("GET", "/api/groups/group-limit"): {"exists": True, "amount": 50},
                    ("POST", "/api/groups/activate-group"): None})
    g.activate_group("g1", True)
    assert g.c.called("POST", "/api/groups/activate-group")


def test_deactivate_never_blocked(ws):
    g = make_guard({("POST", "/api/groups/activate-group"): None})
    g.activate_group("g1", False)  # pausing requires no limit check
    assert g.c.called("POST", "/api/groups/activate-group")


# ---------- velocity watchdog ----------

def _velocity_routes(spent):
    return {
        ("GET", "/api/owner-statistics/today-so-far-statistics"): {"spends": spent},
        ("GET", "/api/campaigns/campaign-info"): {
            "groupsStatus": [{"id": "g1", "status": "Active"}]},
        ("GET", "/api/groups/group-limit"): {"exists": True, "amount": 50},
        ("POST", "/api/groups/activate-group"): None,
    }


def test_velocity_trips_and_pauses(ws):
    ledger.append("campaign.create", {"name": "x"}, "c1")
    g = make_guard(_velocity_routes(spent=40))  # threshold = 30 * 1.3 = 39
    res = g.velocity_check()
    assert res["tripped"] is True
    assert g.c.called("POST", "/api/groups/activate-group")
    assert ledger.entries("guard.velocity_pause")


def test_velocity_not_tripped_at_threshold(ws):
    ledger.append("campaign.create", {"name": "x"}, "c1")
    g = make_guard(_velocity_routes(spent=39))
    res = g.velocity_check()
    assert res["tripped"] is False
    assert not g.c.called("POST", "/api/groups/activate-group")
