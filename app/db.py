"""
SQLite Orders Database
Stores ONLY order transaction metadata: order_id, email, tier, amount, currency, status, created_at.
Strict privacy adherence: NO property data, NO PAN, NO user inputs are EVER stored in the database.
"""

import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, Optional


DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DB_DIR / "orders.db"


def init_db():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                tier TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                status TEXT NOT NULL,
                payment_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS report_tokens (
                token TEXT PRIMARY KEY,
                order_id TEXT,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def save_order(order_data: Dict[str, Any]) -> bool:
    """Idempotently saves or updates an order."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO orders (order_id, email, tier, amount, currency, status, payment_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(order_id) DO UPDATE SET
                status = excluded.status,
                payment_id = excluded.payment_id
            """,
            (
                order_data["order_id"],
                order_data["email"],
                order_data.get("tier", "standard_report"),
                float(order_data.get("amount", 12.0)),
                order_data.get("currency", "USD"),
                order_data.get("status", "completed"),
                order_data.get("payment_id"),
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_order(order_id: str) -> Optional[Dict[str, Any]]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()
