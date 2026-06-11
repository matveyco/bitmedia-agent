import json

from bitmedia_agent import ledger, workspace


def test_append_read_roundtrip(ws):
    ledger.append("test.action", {"a": 1}, "result-id", note="why")
    es = ledger.entries("test.action")
    assert len(es) == 1
    assert es[0]["params"] == {"a": 1}
    assert es[0]["result"] == "result-id"
    assert es[0]["note"] == "why"
    assert es[0]["ts"].endswith("+00:00")  # UTC


def test_append_creates_parent_dirs(ws):
    assert not workspace.ledger_path().exists()
    ledger.append("x", {}, None)
    assert workspace.ledger_path().exists()


def test_today_entries_filters_by_utc_day(ws):
    old = {"ts": "2020-01-01T00:00:00+00:00", "action": "a", "params": {}, "result": None,
           "note": ""}
    workspace.ledger_path().parent.mkdir(parents=True, exist_ok=True)
    workspace.ledger_path().write_text(json.dumps(old) + "\n")
    ledger.append("a", {}, None)
    assert len(ledger.entries("a")) == 2
    assert len(ledger.today_entries("a")) == 1


def test_our_campaign_ids_ignores_non_string_results(ws):
    ledger.append("campaign.create", {"name": "a"}, "id-1")
    ledger.append("campaign.create", {"name": "b"}, {"weird": True})
    assert ledger.our_campaign_ids() == ["id-1"]


def test_entries_skips_blank_lines(ws):
    ledger.append("a", {}, None)
    with workspace.ledger_path().open("a") as f:
        f.write("\n")
    ledger.append("a", {}, None)
    assert len(ledger.entries("a")) == 2
