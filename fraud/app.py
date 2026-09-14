"""Fraud service — AI-driven fraud risk assessment and held payment management."""
import logging
import os
from flask import Flask, jsonify, request

from auth import current_identity, require_auth
from models import (
    create_held_payment,
    get_held_payment,
    init_db,
    list_held_payments,
    update_held_payment_status,
)
from assessment import InsufficientFundsException, assess_payment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fraud")


def create_app():
    app = Flask(__name__)
    init_db()

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.post("/assess")
    @require_auth
    def assess():
        data = request.get_json(silent=True) or {}
        account_id = data.get("account_id")
        amount = data.get("amount")
        description = data.get("description", "")
        beneficiary = data.get("beneficiary", {})

        if not account_id or not amount:
            return jsonify({"error": "missing_required_fields"}), 400

        token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
        user_id = request.identity["user_id"]

        try:
            verdict = assess_payment(
                account_id=account_id,
                amount_str=str(amount),
                description=description,
                beneficiary=beneficiary,
                token=token,
            )
        except InsufficientFundsException as e:
            logger.warning(f"Insufficient funds: {e}")
            return jsonify({"error": "insufficient_funds", "message": str(e)}), 422
        except Exception as e:
            logger.exception("Error assessing payment")
            return jsonify({"error": "assessment_failed", "message": str(e)}), 500

        # If held, persist to fraud database
        if verdict.get("action") == "hold":
            btype = beneficiary.get("type", "external")
            bname = beneficiary.get("name")
            biban = beneficiary.get("iban")
            bacc = beneficiary.get("account_id")

            held_id = create_held_payment(
                user_id=user_id,
                account_id=account_id,
                amount=str(amount),
                description=description,
                beneficiary_type=btype,
                beneficiary_name=bname,
                beneficiary_iban=biban,
                beneficiary_account_id=bacc,
                risk_level=verdict.get("risk_level", "Medium"),
                risk_label=verdict.get("risk_label", "Suspicious"),
                action="hold",
                fraud_type=verdict.get("fraud_type", "Undetermined"),
                red_flags=verdict.get("red_flags", []),
                explanation=verdict.get("explanation", ""),
                status="held",
            )
            verdict["held_payment_id"] = held_id

        return jsonify(verdict)

    @app.get("/held-payments")
    @require_auth
    def get_held_payments():
        user_id = request.identity["user_id"]
        status = request.args.get("status")
        payments = list_held_payments(user_id=user_id, status=status)
        return jsonify(payments)

    @app.get("/held-payments/<int:payment_id>")
    @require_auth
    def get_single_held_payment(payment_id):
        user_id = request.identity["user_id"]
        payment = get_held_payment(payment_id, user_id=user_id)
        if not payment:
            return jsonify({"error": "not_found"}), 404
        return jsonify(payment)

    @app.post("/held-payments/<int:payment_id>/approve")
    @require_auth
    def approve_held_payment(payment_id):
        user_id = request.identity["user_id"]
        payment = get_held_payment(payment_id, user_id=user_id)
        if not payment:
            return jsonify({"error": "not_found"}), 404
        if payment["status"] != "held":
            return jsonify({"error": "invalid_status", "status": payment["status"]}), 400

        update_held_payment_status(payment_id, "approved", user_id=user_id)
        
        # Prepare payment payload for ledger submission
        beneficiary = {"type": payment["beneficiary_type"]}
        if payment["beneficiary_type"] == "internal":
            beneficiary["account_id"] = payment["beneficiary_account_id"]
        else:
            beneficiary["iban"] = payment["beneficiary_iban"]
            beneficiary["name"] = payment["beneficiary_name"]

        payment_payload = {
            "account_id": payment["account_id"],
            "amount": payment["amount"],
            "description": payment["description"],
            "beneficiary": beneficiary,
        }
        return jsonify({"status": "approved", "payment": payment_payload})

    @app.post("/held-payments/<int:payment_id>/reject")
    @require_auth
    def reject_held_payment(payment_id):
        user_id = request.identity["user_id"]
        payment = get_held_payment(payment_id, user_id=user_id)
        if not payment:
            return jsonify({"error": "not_found"}), 404
        if payment["status"] != "held":
            return jsonify({"error": "invalid_status", "status": payment["status"]}), 400

        update_held_payment_status(payment_id, "rejected", user_id=user_id)
        return jsonify({"status": "rejected"})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8084)
