import json
import os
from pathlib import Path
import pytest
import requests

STATEMENTS_URL = os.environ.get("STATEMENTS_URL", "http://localhost:8083")
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def load_fixture(fixture_name: str):
    fixture_path = FIXTURES_DIR / fixture_name
    assert fixture_path.exists(), f"Missing fixture file: {fixture_path}"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


# --- Healthcheck Endpoint Tests ---


def test_healthz():
    url = f"{STATEMENTS_URL}/healthz"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    assert "application/json" in resp.headers.get("Content-Type", "")
    assert resp.json() == load_fixture("healthz.json")
    assert resp.json() == {"status": "ok"}


# --- Detail Statements Endpoint Tests ---


def test_statements_account_1_full():
    url = f"{STATEMENTS_URL}/statements/1"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("statements_account_1_all.json")
    body = resp.json()
    assert body == expected

    # Structural contract assertions
    assert body["account_id"] == "1"
    assert body["from"] is None
    assert body["to"] is None
    assert body["count"] == len(body["transactions"])
    assert body["count"] > 0

    # Field mapping assertions
    for tx in body["transactions"]:
        assert "id" in tx
        assert "type" in tx
        assert "amount" in tx
        assert "counterparty" in tx
        assert "description" in tx
        assert "date" in tx
        assert "created_at" not in tx, "Internal ledger field 'created_at' must be renamed to 'date'"
        assert tx["type"] in ("deposit", "payment_out", "payment_in")


def test_statements_account_2_full():
    url = f"{STATEMENTS_URL}/statements/2"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("statements_account_2_all.json")
    body = resp.json()
    assert body == expected
    assert body["account_id"] == "2"
    assert body["count"] == len(body["transactions"])


def test_statements_filter_type_deposit():
    url = f"{STATEMENTS_URL}/statements/1?type=deposit"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("statements_account_1_deposit.json")
    body = resp.json()
    assert body == expected
    assert all(tx["type"] == "deposit" for tx in body["transactions"])
    assert body["count"] == len(body["transactions"])


def test_statements_filter_type_payment_out():
    url = f"{STATEMENTS_URL}/statements/1?type=payment_out"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("statements_account_1_payment_out.json")
    body = resp.json()
    assert body == expected
    assert all(tx["type"] == "payment_out" for tx in body["transactions"])
    assert body["count"] == len(body["transactions"])


def test_statements_filter_type_payment_in():
    url = f"{STATEMENTS_URL}/statements/1?type=payment_in"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("statements_account_1_payment_in.json")
    body = resp.json()
    assert body == expected
    assert all(tx["type"] == "payment_in" for tx in body["transactions"])
    assert body["count"] == len(body["transactions"])


def test_statements_filter_type_unknown():
    url = f"{STATEMENTS_URL}/statements/1?type=unknown_type"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("statements_account_1_type_unknown.json")
    body = resp.json()
    assert body == expected
    assert body["transactions"] == []
    assert body["count"] == 0


def test_statements_filter_date_from():
    from_date = "2026-09-14T15:26:11.759427+00:00"
    url = f"{STATEMENTS_URL}/statements/1"
    resp = requests.get(url, params={"from": from_date}, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("statements_account_1_from.json")
    body = resp.json()
    assert body == expected
    assert body["from"] == from_date
    assert body["to"] is None


def test_statements_filter_date_to():
    to_date = "2026-09-14T15:26:11.600000+00:00"
    url = f"{STATEMENTS_URL}/statements/1"
    resp = requests.get(url, params={"to": to_date}, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("statements_account_1_to.json")
    body = resp.json()
    assert body == expected
    assert body["from"] is None
    assert body["to"] == to_date


def test_statements_filter_date_from_and_to():
    from_date = "2026-09-14T15:26:11.379640+00:00"
    to_date = "2026-09-14T15:26:11.759427+00:00"
    url = f"{STATEMENTS_URL}/statements/1"
    resp = requests.get(url, params={"from": from_date, "to": to_date}, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("statements_account_1_from_to.json")
    body = resp.json()
    assert body == expected
    assert body["from"] == from_date
    assert body["to"] == to_date


def test_statements_filter_dates_and_type():
    from_date = "2026-09-14T15:26:11.379640+00:00"
    to_date = "2026-09-14T15:26:11.759427+00:00"
    url = f"{STATEMENTS_URL}/statements/1"
    resp = requests.get(
        url,
        params={"from": from_date, "to": to_date, "type": "deposit"},
        timeout=5,
    )
    assert resp.status_code == 200
    expected = load_fixture("statements_account_1_from_to_deposit.json")
    body = resp.json()
    assert body == expected
    assert body["from"] == from_date
    assert body["to"] == to_date
    assert all(tx["type"] == "deposit" for tx in body["transactions"])


def test_statements_empty_account():
    url = f"{STATEMENTS_URL}/statements/99999"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("statements_empty_account_99999.json")
    body = resp.json()
    assert body == expected
    assert body["account_id"] == "99999"
    assert body["transactions"] == []
    assert body["count"] == 0


def test_statements_non_numeric_account():
    url = f"{STATEMENTS_URL}/statements/abc"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("statements_invalid_account_abc.json")
    body = resp.json()
    assert body == expected
    assert body["account_id"] == "abc"
    assert body["transactions"] == []
    assert body["count"] == 0


# --- Summary Endpoint Tests ---


def test_summary_account_1_default():
    url = f"{STATEMENTS_URL}/statements/1/summary"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("summary_account_1_default.json")
    body = resp.json()
    assert body == expected

    # Structural contract assertions
    assert body["account_id"] == "1"
    assert isinstance(body["months"], list)
    for m in body["months"]:
        assert "month" in m
        assert "total_in" in m
        assert "total_out" in m
        assert "net" in m
        # Net must equal total_in - total_out rounded to 2 decimal places
        expected_net = round(m["total_in"] - m["total_out"], 2)
        assert m["net"] == expected_net


def test_summary_account_2_default():
    url = f"{STATEMENTS_URL}/statements/2/summary"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("summary_account_2_default.json")
    body = resp.json()
    assert body == expected
    assert body["account_id"] == "2"


def test_summary_months_parameter_1():
    url = f"{STATEMENTS_URL}/statements/1/summary?months=1"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("summary_account_1_months_1.json")
    body = resp.json()
    assert body == expected
    assert len(body["months"]) <= 1


def test_summary_months_parameter_0():
    url = f"{STATEMENTS_URL}/statements/1/summary?months=0"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("summary_account_1_months_0.json")
    body = resp.json()
    assert body == expected
    assert body["months"] == []


def test_summary_months_parameter_12():
    url = f"{STATEMENTS_URL}/statements/1/summary?months=12"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("summary_account_1_months_12.json")
    body = resp.json()
    assert body == expected


def test_summary_invalid_months_fallback():
    url = f"{STATEMENTS_URL}/statements/1/summary?months=invalid"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("summary_account_1_months_invalid.json")
    default_summary = load_fixture("summary_account_1_default.json")
    body = resp.json()
    assert body == expected
    assert body == default_summary, "Invalid months parameter should fall back to default (6 months)"


def test_summary_ignores_query_params():
    url = f"{STATEMENTS_URL}/statements/1/summary?from=2026-09-01&type=deposit"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("summary_account_1_ignores_query_params.json")
    default_summary = load_fixture("summary_account_1_default.json")
    body = resp.json()
    assert body == expected
    assert body == default_summary, "Summary endpoint must ignore from/to/type query parameters"


def test_summary_empty_account():
    url = f"{STATEMENTS_URL}/statements/99999/summary"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("summary_empty_account_99999.json")
    body = resp.json()
    assert body == expected
    assert body["account_id"] == "99999"
    assert body["months"] == []


def test_summary_non_numeric_account():
    url = f"{STATEMENTS_URL}/statements/abc/summary"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    expected = load_fixture("summary_invalid_account_abc.json")
    body = resp.json()
    assert body == expected
    assert body["account_id"] == "abc"
    assert body["months"] == []


# --- Replay All Golden Fixtures Parametrized ---


GOLDEN_FIXTURE_CASES = [
    ("healthz.json", "/healthz"),
    ("statements_account_1_all.json", "/statements/1"),
    ("statements_account_1_deposit.json", "/statements/1?type=deposit"),
    ("statements_account_1_payment_out.json", "/statements/1?type=payment_out"),
    ("statements_account_1_payment_in.json", "/statements/1?type=payment_in"),
    ("statements_account_1_type_unknown.json", "/statements/1?type=unknown_type"),
    ("statements_account_1_from.json", "/statements/1?from=2026-09-14T15:26:11.759427%2B00:00"),
    ("statements_account_1_to.json", "/statements/1?to=2026-09-14T15:26:11.600000%2B00:00"),
    (
        "statements_account_1_from_to.json",
        "/statements/1?from=2026-09-14T15:26:11.379640%2B00:00&to=2026-09-14T15:26:11.759427%2B00:00",
    ),
    (
        "statements_account_1_from_to_deposit.json",
        "/statements/1?from=2026-09-14T15:26:11.379640%2B00:00&to=2026-09-14T15:26:11.759427%2B00:00&type=deposit",
    ),
    ("statements_account_2_all.json", "/statements/2"),
    ("statements_empty_account_99999.json", "/statements/99999"),
    ("statements_invalid_account_abc.json", "/statements/abc"),
    ("summary_account_1_default.json", "/statements/1/summary"),
    ("summary_account_1_months_1.json", "/statements/1/summary?months=1"),
    ("summary_account_1_months_0.json", "/statements/1/summary?months=0"),
    ("summary_account_1_months_12.json", "/statements/1/summary?months=12"),
    ("summary_account_1_months_invalid.json", "/statements/1/summary?months=invalid"),
    ("summary_account_1_ignores_query_params.json", "/statements/1/summary?from=2026-09-01&type=deposit"),
    ("summary_account_2_default.json", "/statements/2/summary"),
    ("summary_empty_account_99999.json", "/statements/99999/summary"),
    ("summary_invalid_account_abc.json", "/statements/abc/summary"),
]


@pytest.mark.parametrize("fixture_name,path", GOLDEN_FIXTURE_CASES)
def test_replay_golden_fixture(fixture_name, path):
    url = f"{STATEMENTS_URL}{path}"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200, f"Expected 200 OK for {path}, got {resp.status_code}"
    expected = load_fixture(fixture_name)
    assert resp.json() == expected, f"Response mismatch against fixture {fixture_name}"
