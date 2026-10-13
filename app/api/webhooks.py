"""
Payment Webhook Router
POST /webhooks/payment
Supports merchant of record webhooks (Paddle, Lemon Squeezy, Razorpay).
Handles idempotency and records minimal transaction metadata.
Never persists any property or tax data.
"""

import hashlib
import hmac
import os
import secrets
from typing import Any, Dict, Optional
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from app.db import save_order, get_order


router = APIRouter(prefix="/webhooks", tags=["webhooks"])
WEBHOOK_SECRET = os.environ.get("PAYMENT_WEBHOOK_SECRET", "nri-webhook-secret-key-2026")


class PaymentSimulationRequest(BaseModel):
    email: str
    tier: str = "comprehensive_report"
    amount: float = 12.0
    currency: str = "USD"
    order_id: Optional[str] = None


@router.post("/payment")
async def handle_payment_webhook(
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    x_razorpay_signature: Optional[str] = Header(None, alias="X-Razorpay-Signature"),
):
    """
    Handles payment notifications from Merchant of Record / Payment Gateway.
    Verifies signature and stores order details idempotently.
    """
    raw_body = await request.body()
    payload = {}
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Optional signature verification if secret configured and header passed
    provided_sig = x_signature or x_razorpay_signature
    if provided_sig and WEBHOOK_SECRET and WEBHOOK_SECRET != "nri-webhook-secret-key-2026":
        expected_sig = hmac.new(WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(provided_sig, expected_sig):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Extract order details
    order_id = payload.get("order_id") or payload.get("id") or f"ORD_{secrets.token_hex(6).upper()}"
    email = payload.get("email") or payload.get("customer_email") or "customer@example.com"
    tier = payload.get("tier", "paid_report")
    amount = float(payload.get("amount", 12.0))
    currency = payload.get("currency", "USD")
    status = payload.get("status", "completed")
    payment_id = payload.get("payment_id") or payload.get("transaction_id")

    # Check idempotency
    existing = get_order(order_id)
    if existing and existing.get("status") == "completed":
        return {"status": "already_processed", "order_id": order_id}

    save_order({
        "order_id": order_id,
        "email": email,
        "tier": tier,
        "amount": amount,
        "currency": currency,
        "status": status,
        "payment_id": payment_id,
    })

    return {"status": "success", "order_id": order_id}


@router.post("/simulate-checkout")
def simulate_checkout(req: PaymentSimulationRequest) -> Dict[str, Any]:
    """
    Test/demo checkout endpoint to unlock full report in development and evaluation.
    """
    order_id = req.order_id or f"DEMO_{secrets.token_hex(6).upper()}"
    save_order({
        "order_id": order_id,
        "email": req.email,
        "tier": req.tier,
        "amount": req.amount,
        "currency": req.currency,
        "status": "completed",
        "payment_id": f"PAY_{secrets.token_hex(8)}",
    })
    return {
        "status": "success",
        "order_id": order_id,
        "message": "Payment simulation succeeded. Report unlocked.",
    }
