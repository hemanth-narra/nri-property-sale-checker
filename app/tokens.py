"""
Cryptographic Token Utility
Generates and validates signed report tokens using standard library hashlib and hmac.
"""

from datetime import datetime, timedelta
import hashlib
import hmac
import os
import secrets
import sqlite3
from typing import Optional

from app.db import init_db, DB_PATH


SECRET_KEY = os.environ.get("REPORT_TOKEN_SECRET", "nri-property-sale-checker-secret-key-2026")


def create_signed_token(order_id: str, email: str = "") -> str:
    """Creates a cryptographic token valid for 24 hours."""
    raw = f"{order_id}:{email}:{secrets.token_hex(16)}:{datetime.now().isoformat()}"
    sig = hmac.new(SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()
    token = f"{secrets.token_hex(8)}_{sig[:24]}"

    init_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        expires = datetime.now() + timedelta(hours=24)
        cur.execute(
            "INSERT INTO report_tokens (token, order_id, email, expires_at) VALUES (?, ?, ?, ?)",
            (token, order_id, email, expires.isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    return token


def verify_token(token: str) -> Optional[dict]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM report_tokens WHERE token = ?", (token,))
        row = cur.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()
