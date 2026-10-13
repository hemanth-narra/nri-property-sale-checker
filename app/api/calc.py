"""
Calculation API Router
POST /api/calc
Strictly stateless: Computes in-memory, persists NO property data, logs NO personal details or PAN.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.engine.calculator import calculate_nri_property_sale, load_rules


router = APIRouter(prefix="/api", tags=["calculation"])


class CalculationRequest(BaseModel):
    residential_status: str = Field(..., description="non_resident, resident, rnor")
    property_type: str = Field(..., description="residential, plot, commercial, agricultural")
    transfer_date: str = Field("2026-10-15", description="YYYY-MM-DD")
    acquisition_date: str = Field("2016-04-10", description="YYYY-MM-DD")
    mode_of_acquisition: str = Field("purchase", description="purchase, inheritance, gift")
    sale_consideration: float = Field(..., ge=0, description="Agreed sale price in INR")
    stamp_duty_value: Optional[float] = Field(None, ge=0, description="Stamp duty or circle rate in INR")
    cost_of_acquisition: float = Field(0.0, ge=0, description="Original purchase cost in INR")
    cost_of_improvement: float = Field(0.0, ge=0, description="Improvement cost in INR")
    transfer_expenses: float = Field(0.0, ge=0, description="Transfer expenses / brokerage in INR")
    ownership_share: float = Field(100.0, gt=0, le=100.0, description="Percentage of ownership share (1-100)")
    other_indian_income: float = Field(0.0, ge=0, description="Other taxable income in India for FY")
    pan_available: bool = Field(True, description="Whether seller has valid Indian PAN")
    buyer_type: str = Field("resident_individual_huf", description="resident_individual_huf, company_llp_firm, non_resident")
    source_of_funds: str = Field("nre_fcnr", description="nre_fcnr, nro_rupee, acquired_resident, inherited")
    fy_remittances_already_made_usd: float = Field(0.0, ge=0, description="USD remitted from NRO in current FY")


@router.post("/calc")
def calculate_property_tax(req: CalculationRequest) -> Dict[str, Any]:
    """
    Computes capital gains, tax liability, TDS withholding, lower-deduction target,
    exemption scenarios, and repatriation channel based on input parameters.
    No property inputs or PAN are ever saved to disk or database.
    """
    payload = req.model_dump()
    if payload.get("stamp_duty_value") is None:
        payload["stamp_duty_value"] = payload["sale_consideration"]

    result = calculate_nri_property_sale(payload)
    return result


@router.get("/rules-meta")
def get_rules_metadata(transfer_date: Optional[str] = "2026-10-15") -> Dict[str, Any]:
    """
    Returns the version, last verified date, and governing law citations for a given date.
    """
    rules = load_rules(transfer_date or "2026-10-15")
    return {
        "version": rules.get("version"),
        "law_name": rules.get("law_name"),
        "effective_from": rules.get("effective_from"),
        "last_verified": rules.get("last_verified"),
        "verify_flags": rules.get("verify_flags", []),
        "cbdt_notification": rules.get("tds", {}).get("cbdt_notification"),
        "ltcg_rate_percent": rules.get("ltcg_property", {}).get("rate", 0.125) * 100,
        "cess_percent": rules.get("cess", 0.04) * 100,
    }
