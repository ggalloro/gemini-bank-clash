"""AI-driven fraud risk assessment using Gemini 3.7 Flash and ledger account context."""
import json
import logging
import os
import requests
from google import genai
from pydantic import BaseModel

logger = logging.getLogger(__name__)

LEDGER_URL = os.environ.get("LEDGER_URL", "http://localhost:8082")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.7-flash")
TIMEOUT_SECONDS = 20.0


class InsufficientFundsException(Exception):
    """Raised when payment amount exceeds current account balance."""
    pass


class RedFlag(BaseModel):
    flag: str
    reason: str


class FraudAssessmentResult(BaseModel):
    risk_level: str  # "High", "Medium", "Low"
    action: str      # "hold", "approve"
    fraud_type: str
    red_flags: list[RedFlag]
    explanation: str


SYSTEM_INSTRUCTION = """
You are an expert fraud protection AI for Gemini Bank.
Your job is to assess outgoing payments for fraud risk before any money moves.

Evaluate the payment context, the account's current balance, and recent transaction history.

### Verdict Levels:
- High: "High risk" -> action is "hold". Strong indicators of fraud, extreme behavioral deviation, or dangerous language cues.
- Medium: "Suspicious" -> action is "hold". Noticeable red flags, pressure tactics, unusual amount, or unfamiliar payee with anomalies.
- Low: "No clear risk" -> action is "approve". Typical everyday transactions, routine merchants, known recipients, normal transfer patterns.

### Payment-Fraud Taxonomy:
Classify into the single most likely category:
- Authorized push payment (APP) fraud — customer tricked into sending money themselves
- Invoice / mandate redirection — changed bank/landlord details
- Impersonation — impersonating bank, police, or government agency
- Investment / crypto scam — too-good-to-be-true returns, guaranteed profit, urgency
- Romance scam — emotional manipulation leading to money requests
- Purchase / marketplace scam — paying for goods that won't arrive
- Money-mule — moving funds on someone else's behalf
- Undetermined — suspicious but no clear category
- Legitimate — no fraud indicators

### Bank Risk Criteria & Red Flags:
1. Behavioural signals:
   - Payment is large relative to current account balance (> ~80%).
   - Payment is far larger than typical payment in transaction history.
   - First-time beneficiary (beneficiary not present in history).
   - Out-of-character destination or sudden frequency change.
2. Contextual / Language red flags:
   - Urgency & pressure: "act now", "within the hour", threat of loss.
   - Secrecy: "don't tell anyone", "keep confidential", "do not tell bank".
   - Gift cards / vouchers: requests to buy gift cards or voucher codes.
   - Investment / crypto bait: guaranteed returns, crypto opportunities.
   - Impersonation cues: claims from bank security/fraud team, law enforcement, release fee.
   - Romance / emotional manipulation.
   - Unusual beneficiary: personal name when expecting business or odd reference.

Language red flags alone can trigger a hold even if the amount is small.

Provide a short, reassuring plain-language explanation directly addressing the account owner (not a fraud analyst), explaining why the payment was approved or held.
"""


def get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("NANOBANANA_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def fetch_account_context(account_id, token):
    """Fetch current balance and recent transactions from ledger service."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    # 1. Account detail (with auth)
    acc_resp = requests.get(
        f"{LEDGER_URL}/accounts/{account_id}",
        headers=headers,
        timeout=10,
    )
    if acc_resp.status_code != 200:
        raise ValueError(f"Failed to fetch account {account_id}: status {acc_resp.status_code}")
    account_data = acc_resp.json()

    # 2. Transaction history (internal endpoint)
    txns_resp = requests.get(
        f"{LEDGER_URL}/internal/transactions",
        params={"account_id": account_id},
        timeout=10,
    )
    txns_data = txns_resp.json().get("transactions", []) if txns_resp.status_code == 200 else []

    return account_data, txns_data


def assess_payment(account_id, amount_str, description, beneficiary, token):
    """
    Enriches payment with ledger context, verifies funds, and queries Gemini.
    Applies 20s timeout and error boundary: holds external payments if AI unreachable.
    """
    # 1. Context enrichment from ledger
    account_data, transactions = fetch_account_context(account_id, token)

    current_balance = float(account_data.get("balance", "0.00"))
    payment_amount = float(amount_str)

    # Business Rule 4: Refuse insufficient funds immediately before any AI assessment
    if payment_amount > current_balance:
        raise InsufficientFundsException(
            f"Insufficient funds: payment {payment_amount:.2f} exceeds balance {current_balance:.2f}"
        )

    btype = beneficiary.get("type", "external") if beneficiary else "external"

    # Fallback verdict generator for error boundary
    def make_fallback_verdict(reason_msg):
        if btype == "internal":
            return {
                "risk_level": "Low",
                "risk_label": "No clear risk",
                "action": "approve",
                "fraud_type": "Legitimate",
                "red_flags": [],
                "explanation": "Internal transfer permitted while AI service is temporarily unavailable.",
            }
        else:
            return {
                "risk_level": "Medium",
                "risk_label": "Suspicious",
                "action": "hold",
                "fraud_type": "Undetermined",
                "red_flags": [
                    {
                        "flag": "AI Safeguard Triggered",
                        "reason": f"AI assessment unavailable: {reason_msg}. External payments held for protection.",
                    }
                ],
                "explanation": "Our automated AI fraud detection was temporarily unreachable. To protect your account, this external payment has been held for review.",
            }

    # 2. Prepare AI assessment prompt
    # Summarize history for prompt
    history_summary = []
    for tx in transactions[:30]:
        history_summary.append({
            "type": tx.get("type"),
            "amount": tx.get("amount"),
            "counterparty": tx.get("counterparty"),
            "description": tx.get("description"),
            "created_at": tx.get("created_at"),
        })

    prompt_content = {
        "candidate_payment": {
            "account_id": account_id,
            "account_name": account_data.get("name"),
            "account_iban": account_data.get("iban"),
            "current_balance": f"€{current_balance:.2f}",
            "payment_amount": f"€{payment_amount:.2f}",
            "description": description or "",
            "beneficiary": beneficiary,
        },
        "recent_transactions_sample": history_summary,
    }

    # 3. Call Gemini with 20s timeout boundary
    try:
        client = get_gemini_client()
        if not client:
            logger.warning("Gemini API key is not configured; triggering fallback error boundary.")
            return make_fallback_verdict("Missing API key")

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                SYSTEM_INSTRUCTION,
                f"Assess this candidate payment in JSON:\n{json.dumps(prompt_content, indent=2)}",
            ],
            config=dict(
                response_mime_type="application/json",
                response_schema=FraudAssessmentResult,
            ),
        )

        verdict_data = json.loads(response.text)

        # Normalize verdict fields
        risk_raw = verdict_data.get("risk_level", "Low").strip()
        if "High" in risk_raw:
            risk_level = "High"
            risk_label = "High risk"
            action = "hold"
        elif "Med" in risk_raw or "Suspicious" in risk_raw:
            risk_level = "Medium"
            risk_label = "Suspicious"
            action = "hold"
        else:
            risk_level = "Low"
            risk_label = "No clear risk"
            action = "approve"

        flags = []
        for f in verdict_data.get("red_flags", []):
            if isinstance(f, dict):
                flags.append({"flag": f.get("flag", "Flag"), "reason": f.get("reason", "")})

        fraud_type = verdict_data.get("fraud_type", "Legitimate" if action == "approve" else "Undetermined")
        explanation = verdict_data.get("explanation", "").strip()

        return {
            "risk_level": risk_level,
            "risk_label": risk_label,
            "action": action,
            "fraud_type": fraud_type,
            "red_flags": flags,
            "explanation": explanation,
        }

    except Exception as e:
        logger.exception("Error or timeout calling Gemini API; falling back to safe hold.")
        return make_fallback_verdict(str(e))
