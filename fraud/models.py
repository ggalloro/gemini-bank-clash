"""SQLite persistence for the fraud service."""
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("FRAUD_DB", "fraud.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS held_payments (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                INTEGER NOT NULL,
    account_id             INTEGER NOT NULL,
    amount                 TEXT NOT NULL,
    description            TEXT,
    beneficiary_type       TEXT NOT NULL,
    beneficiary_name       TEXT,
    beneficiary_iban       TEXT,
    beneficiary_account_id INTEGER,
    risk_level             TEXT NOT NULL,
    risk_label             TEXT NOT NULL,
    action                 TEXT NOT NULL,
    fraud_type             TEXT NOT NULL,
    red_flags              TEXT NOT NULL,
    explanation            TEXT NOT NULL,
    status                 TEXT NOT NULL DEFAULT 'held',
    created_at             TEXT NOT NULL,
    resolved_at            TEXT
);
"""


def get_db():
    # Ensure directory exists if DB_PATH contains a directory
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def row_to_dict(row):
    if row is None:
        return None
    d = dict(row)
    if "red_flags" in d and isinstance(d["red_flags"], str):
        try:
            d["red_flags"] = json.loads(d["red_flags"])
        except Exception:
            d["red_flags"] = []
    if "risk_label" not in d or not d["risk_label"]:
        rl = d.get("risk_level", "Low")
        d["risk_label"] = "High risk" if rl == "High" else ("Suspicious" if rl == "Medium" else "No clear risk")
    return d


def create_held_payment(
    user_id,
    account_id,
    amount,
    description,
    beneficiary_type,
    beneficiary_name,
    beneficiary_iban,
    beneficiary_account_id,
    risk_level,
    risk_label,
    action,
    fraud_type,
    red_flags,
    explanation,
    status="held",
):
    conn = get_db()
    try:
        cur = conn.execute(
            """
            INSERT INTO held_payments (
                user_id, account_id, amount, description,
                beneficiary_type, beneficiary_name, beneficiary_iban, beneficiary_account_id,
                risk_level, risk_label, action, fraud_type, red_flags, explanation,
                status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                account_id,
                amount,
                description,
                beneficiary_type,
                beneficiary_name,
                beneficiary_iban,
                beneficiary_account_id,
                risk_level,
                risk_label,
                action,
                fraud_type,
                json.dumps(red_flags),
                explanation,
                status,
                now_iso(),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_held_payment(payment_id, user_id=None):
    conn = get_db()
    try:
        if user_id is not None:
            row = conn.execute(
                "SELECT * FROM held_payments WHERE id = ? AND user_id = ?",
                (payment_id, user_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM held_payments WHERE id = ?", (payment_id,)
            ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def list_held_payments(user_id=None, status=None):
    conn = get_db()
    try:
        query = "SELECT * FROM held_payments"
        params = []
        conditions = []
        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY id DESC"

        rows = conn.execute(query, params).fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


def update_held_payment_status(payment_id, status, user_id=None):
    conn = get_db()
    try:
        resolved = now_iso() if status in ("approved", "rejected") else None
        if user_id is not None:
            cur = conn.execute(
                "UPDATE held_payments SET status = ?, resolved_at = ? WHERE id = ? AND user_id = ?",
                (status, resolved, payment_id, user_id),
            )
        else:
            cur = conn.execute(
                "UPDATE held_payments SET status = ?, resolved_at = ? WHERE id = ?",
                (status, resolved, payment_id),
            )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
