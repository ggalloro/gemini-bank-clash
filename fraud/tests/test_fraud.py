import json
from unittest.mock import patch, MagicMock
import pytest


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_auth_required(client):
    resp = client.post("/assess", json={"account_id": 1, "amount": "100.00"})
    assert resp.status_code == 401

    resp = client.get("/held-payments")
    assert resp.status_code == 401


@patch("assessment.requests.get")
def test_insufficient_funds_rejected_before_ai(mock_get, client, auth_header):
    # Mock account balance = 50.00, payment amount = 100.00
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"id": 1, "balance": "50.00", "iban": "DE123", "name": "Checking"}
    )

    resp = client.post(
        "/assess",
        json={
            "account_id": 1,
            "amount": "100.00",
            "description": "Too large",
            "beneficiary": {"type": "external", "name": "Shop", "iban": "DE999"},
        },
        headers=auth_header,
    )
    assert resp.status_code == 422
    data = resp.get_json()
    assert data["error"] == "insufficient_funds"


@patch("assessment.requests.get")
@patch("assessment.get_gemini_client")
def test_normal_payment_approved(mock_get_gemini, mock_get, client, auth_header):
    # Mock ledger calls
    def get_side_effect(url, **kwargs):
        if "/accounts/1" in url:
            return MagicMock(status_code=200, json=lambda: {"id": 1, "balance": "1000.00", "name": "Checking", "iban": "DE123"})
        if "/internal/transactions" in url:
            return MagicMock(status_code=200, json=lambda: {"transactions": []})
        return MagicMock(status_code=404)

    mock_get.side_effect = get_side_effect

    # Mock Gemini response
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(
        text=json.dumps({
            "risk_level": "Low",
            "action": "approve",
            "fraud_type": "Legitimate",
            "red_flags": [],
            "explanation": "Routine grocery payment within normal limits."
        })
    )
    mock_get_gemini.return_value = mock_client

    resp = client.post(
        "/assess",
        json={
            "account_id": 1,
            "amount": "15.00",
            "description": "SuperMart groceries",
            "beneficiary": {"type": "external", "name": "SuperMart", "iban": "DE8937"},
        },
        headers=auth_header,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["action"] == "approve"
    assert data["risk_level"] == "Low"
    assert "held_payment_id" not in data


@patch("assessment.requests.get")
@patch("assessment.get_gemini_client")
def test_suspicious_payment_held_and_persisted(mock_get_gemini, mock_get, client, auth_header):
    def get_side_effect(url, **kwargs):
        if "/accounts/1" in url:
            return MagicMock(status_code=200, json=lambda: {"id": 1, "balance": "1000.00", "name": "Checking", "iban": "DE123"})
        if "/internal/transactions" in url:
            return MagicMock(status_code=200, json=lambda: {"transactions": []})
        return MagicMock(status_code=404)

    mock_get.side_effect = get_side_effect

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(
        text=json.dumps({
            "risk_level": "High",
            "action": "hold",
            "fraud_type": "Authorized push payment (APP) fraud",
            "red_flags": [
                {"flag": "Urgency & pressure", "reason": "Demands immediate transfer"},
                {"flag": "Gift cards / vouchers", "reason": "Requesting gift card purchases"}
            ],
            "explanation": "This payment shows severe red flags consistent with gift-card fraud."
        })
    )
    mock_get_gemini.return_value = mock_client

    resp = client.post(
        "/assess",
        json={
            "account_id": 1,
            "amount": "180.00",
            "description": "URGENT: buy gift cards",
            "beneficiary": {"type": "external", "name": "GiftCard Rewards Ltd", "iban": "DE911"},
        },
        headers=auth_header,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["action"] == "hold"
    assert data["risk_level"] == "High"
    assert data["fraud_type"] == "Authorized push payment (APP) fraud"
    assert len(data["red_flags"]) == 2
    assert "held_payment_id" in data
    held_id = data["held_payment_id"]

    # Verify listing held payments
    list_resp = client.get("/held-payments", headers=auth_header)
    assert list_resp.status_code == 200
    held_list = list_resp.get_json()
    assert len(held_list) == 1
    assert held_list[0]["id"] == held_id
    assert held_list[0]["status"] == "held"

    # Verify get single held payment
    detail_resp = client.get(f"/held-payments/{held_id}", headers=auth_header)
    assert detail_resp.status_code == 200
    assert detail_resp.get_json()["amount"] == "180.00"

    # Approve held payment
    approve_resp = client.post(f"/held-payments/{held_id}/approve", headers=auth_header)
    assert approve_resp.status_code == 200
    appr_data = approve_resp.get_json()
    assert appr_data["status"] == "approved"
    assert appr_data["payment"]["amount"] == "180.00"

    # Check status updated
    detail_resp2 = client.get(f"/held-payments/{held_id}", headers=auth_header)
    assert detail_resp2.get_json()["status"] == "approved"


@patch("assessment.requests.get")
@patch("assessment.get_gemini_client")
def test_fallback_error_boundary(mock_get_gemini, mock_get, client, auth_header):
    # Simulate Gemini failure/timeout
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {"id": 1, "balance": "1000.00", "transactions": []})
    mock_get_gemini.side_effect = Exception("Gemini connection error")

    # 1. External payment should be HELD when AI is unreachable
    resp_ext = client.post(
        "/assess",
        json={
            "account_id": 1,
            "amount": "50.00",
            "description": "External payment",
            "beneficiary": {"type": "external", "name": "External Merchant", "iban": "DE999"},
        },
        headers=auth_header,
    )
    assert resp_ext.status_code == 200
    data_ext = resp_ext.get_json()
    assert data_ext["action"] == "hold"
    assert "held_payment_id" in data_ext
    assert "temporarily unreachable" in data_ext["explanation"]

    # 2. Internal payment should be APPROVED when AI is unreachable
    resp_int = client.post(
        "/assess",
        json={
            "account_id": 1,
            "amount": "50.00",
            "description": "Internal transfer",
            "beneficiary": {"type": "internal", "account_id": 2},
        },
        headers=auth_header,
    )
    assert resp_int.status_code == 200
    data_int = resp_int.get_json()
    assert data_int["action"] == "approve"
    assert "held_payment_id" not in data_int
