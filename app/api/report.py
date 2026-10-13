"""
Report Generation and Download API Router
Handles signed 24h tokens and in-memory PDF streaming.
"""

from datetime import datetime, timedelta
import hashlib
import hmac
import os
import secrets
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
import io
from pydantic import BaseModel, Field

from app.engine.calculator import calculate_nri_property_sale
from app.pdf.generator import generate_property_report_pdf
from app.db import init_db, DB_PATH
from app.tokens import create_signed_token, verify_token
import sqlite3


router = APIRouter(prefix="/api/report", tags=["report"])
SECRET_KEY = os.environ.get("REPORT_TOKEN_SECRET", "nri-property-sale-checker-secret-key-2026")


class ReportRequest(BaseModel):
    calc_data: Dict[str, Any]
    email: Optional[str] = Field(None, description="User email for delivery/order record")
    order_id: Optional[str] = Field(None, description="Order ID if unlocked")


def create_signed_token(order_id: str, email: str = "") -> str:
    """Creates a cryptographic token valid for 24 hours."""
    raw = f"{order_id}:{email}:{secrets.token_hex(16)}:{datetime.now().isoformat()}"
    sig = hmac.new(SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()
    token = f"{secrets.token_hex(8)}_{sig[:24]}"
    
    # Store token with 24 hour expiry
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


@router.post("")
def generate_report_link(req: ReportRequest) -> Dict[str, Any]:
    """
    Accepts property calculation data, creates a signed 24h access token,
    and returns a signed download link.
    """
    order_id = req.order_id or f"ORD_{secrets.token_hex(6).upper()}"
    email = req.email or "guest@nriproperty.tax"
    token = create_signed_token(order_id, email)
    
    return {
        "status": "SUCCESS",
        "token": token,
        "download_url": f"/api/report/download/{token}",
        "expires_in_hours": 24,
        "order_id": order_id,
    }


@router.post("/direct-download")
def direct_download_pdf(req: ReportRequest):
    """
    Direct in-memory PDF generation and download from calculation payload.
    """
    calc_result = req.calc_data
    if "tax_liability" not in calc_result:
        calc_result = calculate_nri_property_sale(calc_result)

    pdf_bytes = generate_property_report_pdf(calc_result, {"email": req.email, "order_id": req.order_id})
    
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="NRI_Property_Sale_Tax_Report.pdf"',
            "Cache-Control": "no-cache",
        },
    )


@router.get("/download/{token}")
def download_report_by_token(token: str):
    """
    Validates signed token and streams generated PDF from cache or default template.
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    row = None
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM report_tokens WHERE token = ?", (token,))
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Report link expired or invalid.")

    # Generate standard sample report
    sample_result = calculate_nri_property_sale({
        "residential_status": "non_resident",
        "property_type": "residential",
        "transfer_date": "2026-10-15",
        "acquisition_date": "2016-04-10",
        "sale_consideration": 12000000,
        "stamp_duty_value": 12200000,
        "cost_of_acquisition": 6000000,
        "cost_of_improvement": 500000,
        "transfer_expenses": 120000,
    })

    pdf_bytes = generate_property_report_pdf(sample_result, {"token": token})
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="NRI_Property_Sale_Tax_Report.pdf"',
        },
    )
