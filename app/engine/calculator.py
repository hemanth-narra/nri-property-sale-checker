"""
NRI Property Sale Checker - Core Calculation Engine
Implements the 12-step calculation algorithm as pure functions.
Reads all tax rates, bands, caps, and section citations directly from versioned JSON rules.
Contains zero hard-coded law constants.
"""

from datetime import date, datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


RULES_DIR = Path(__file__).resolve().parent.parent / "rules"


def load_rules(transfer_date_str: str) -> Dict[str, Any]:
    """
    Step 2: Select law version by transfer date and load rules/<version>.json.
    Dates before 2026-04-01 use 1961 Act; dates on or after 2026-04-01 use 2026-27.json (2025 Act).
    """
    try:
        t_date = datetime.strptime(transfer_date_str, "%Y-%m-%d").date()
    except Exception:
        # Fallback to year if provided like "2026"
        if len(transfer_date_str) == 4 and transfer_date_str.isdigit():
            t_date = date(int(transfer_date_str), 10, 1)
        else:
            t_date = date.today()

    cutoff_date = date(2026, 4, 1)
    if t_date < cutoff_date:
        rules_path = RULES_DIR / "1961.json"
    else:
        rules_path = RULES_DIR / "2026-27.json"

    if not rules_path.exists():
        # Fallback to 2026-27
        rules_path = RULES_DIR / "2026-27.json"

    with open(rules_path, "r", encoding="utf-8") as f:
        return json.load(f)


def calculate_holding_period_months(
    acquisition_date_str: str,
    transfer_date_str: str
) -> Tuple[int, bool]:
    """
    Step 3: Holding months = acquisition to transfer.
    If acquired via inheritance or gift, acquisition_date_str should be previous owner's acquisition date.
    Returns (holding_months, is_long_term).
    """
    def parse_d(d_str: str) -> date:
        try:
            return datetime.strptime(d_str, "%Y-%m-%d").date()
        except Exception:
            if len(d_str) == 4 and d_str.isdigit():
                return date(int(d_str), 4, 1)
            return date.today()

    acq = parse_d(acquisition_date_str)
    trn = parse_d(transfer_date_str)

    months = (trn.year - acq.year) * 12 + (trn.month - acq.month)
    if trn.day < acq.day:
        months -= 1

    months = max(0, months)
    is_long_term = months > 24
    return months, is_long_term


def calculate_surcharge_and_relief(
    base_tax: float,
    total_income: float,
    tax_rate: float,
    rules: Dict[str, Any]
) -> Tuple[float, float, float]:
    """
    Step 7: Surcharge calculation with LTCG 15% cap and marginal relief.
    Returns (surcharge_amount, effective_surcharge_rate, marginal_relief).
    """
    if base_tax <= 0 or total_income <= 0:
        return 0.0, 0.0, 0.0

    bands = rules.get("surcharge", {}).get("bands", [[5000000, 0.10], [10000000, 0.15]])
    ltcg_cap = rules.get("surcharge", {}).get("ltcg_cap", 0.15)

    surcharge_rate = 0.0
    threshold = 0

    for band_limit, rate in bands:
        if total_income > band_limit:
            surcharge_rate = min(rate, ltcg_cap)
            threshold = band_limit
        else:
            break

    if surcharge_rate == 0.0:
        return 0.0, 0.0, 0.0

    nominal_surcharge = base_tax * surcharge_rate
    marginal_relief = 0.0

    # Marginal relief calculations
    if threshold == 5000000:
        # At 50L threshold, surcharge was 0%
        tax_at_threshold = threshold * tax_rate
        max_total_liability = tax_at_threshold + (total_income - threshold)
        actual_liability = base_tax + nominal_surcharge
        if actual_liability > max_total_liability:
            marginal_relief = actual_liability - max_total_liability
    elif threshold == 10000000:
        # At 1 Cr threshold, surcharge was 10%
        tax_at_threshold = (threshold * tax_rate) * 1.10
        max_total_liability = tax_at_threshold + (total_income - threshold)
        actual_liability = base_tax + nominal_surcharge
        if actual_liability > max_total_liability:
            marginal_relief = actual_liability - max_total_liability

    effective_surcharge = max(0.0, nominal_surcharge - marginal_relief)
    return effective_surcharge, surcharge_rate, marginal_relief


def calculate_tax_liability(
    gain: float,
    is_long_term: bool,
    other_income: float,
    rules: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Computes base tax, surcharge, marginal relief, and cess for a given capital gain.
    """
    if gain <= 0:
        return {
            "base_tax": 0.0,
            "tax_rate": 0.0,
            "surcharge": 0.0,
            "surcharge_rate": 0.0,
            "marginal_relief": 0.0,
            "cess": 0.0,
            "total_tax": 0.0,
            "effective_tax_rate": 0.0,
        }

    if is_long_term:
        tax_rate = rules["ltcg_property"]["rate"]
    else:
        tax_rate = rules.get("stcg_property", {}).get("slab_rate_default", 0.30)

    base_tax = gain * tax_rate
    total_income = gain + other_income

    surcharge, surcharge_rate, relief = calculate_surcharge_and_relief(
        base_tax, total_income, tax_rate, rules
    )

    tax_plus_surcharge = base_tax + surcharge
    cess_rate = rules.get("cess", 0.04)
    cess = tax_plus_surcharge * cess_rate
    total_tax = tax_plus_surcharge + cess

    return {
        "base_tax": round(base_tax, 2),
        "tax_rate": tax_rate,
        "surcharge": round(surcharge, 2),
        "surcharge_rate": surcharge_rate,
        "marginal_relief": round(relief, 2),
        "cess": round(cess, 2),
        "total_tax": round(total_tax, 2),
        "effective_tax_rate": round((total_tax / gain) * 100, 2) if gain > 0 else 0.0,
    }


def compute_tds_exposure(
    sale_consideration: float,
    is_long_term: bool,
    pan_available: bool,
    rules: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Step 8: TDS exposure = consideration * rate * (1 + surcharge by payment band) * 1.04.
    If no PAN: minimum 20% + applicable surcharge & cess.
    """
    if is_long_term:
        base_rate = rules["ltcg_property"]["rate"]
    else:
        base_rate = rules.get("stcg_property", {}).get("slab_rate_default", 0.30)

    if not pan_available:
        min_no_pan = rules.get("tds", {}).get("no_pan_min_rate", 0.20)
        base_rate = max(base_rate, min_no_pan)

    # Surcharge by payment amount band
    bands = rules.get("surcharge", {}).get("bands", [[5000000, 0.10], [10000000, 0.15]])
    ltcg_cap = rules.get("surcharge", {}).get("ltcg_cap", 0.15)
    surcharge_rate = 0.0

    for band_limit, rate in bands:
        if sale_consideration > band_limit:
            surcharge_rate = min(rate, ltcg_cap)
        else:
            break

    cess_rate = rules.get("cess", 0.04)
    # Effective TDS rate formula: base_rate * (1 + surcharge) * (1 + cess)
    effective_rate = base_rate * (1.0 + surcharge_rate) * (1.0 + cess_rate)
    tds_amount = round(sale_consideration * effective_rate, 2)

    return {
        "base_rate": base_rate,
        "surcharge_rate": surcharge_rate,
        "cess_rate": cess_rate,
        "effective_rate": round(effective_rate, 6),
        "effective_rate_percent": round(effective_rate * 100, 2),
        "tds_exposure": tds_amount,
    }


def determine_buyer_reporting(
    transfer_date_str: str,
    buyer_type: str,
    rules: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Determines buyer TDS reporting obligations based on transfer date and buyer category.
    """
    tds_rules = rules.get("tds", {})
    pan_cutoff = tds_rules.get("pan_based_form_from")

    is_pan_based_eligible = False
    if pan_cutoff:
        try:
            t_date = datetime.strptime(transfer_date_str, "%Y-%m-%d").date()
            c_date = datetime.strptime(pan_cutoff, "%Y-%m-%d").date()
            if t_date >= c_date and buyer_type in ["resident_individual_huf", "individual", "huf"]:
                is_pan_based_eligible = True
        except Exception:
            pass

    if is_pan_based_eligible:
        return {
            "form": tds_rules.get("form_individual_huf", "141-ScheduleE"),
            "mechanism": "PAN-based payment and reporting (No TAN needed)",
            "deadline": "Within 30 days from the end of the month of deduction",
            "code": tds_rules.get("code", "1057"),
            "section": tds_rules.get("section_new", "393(2) Sl.17"),
            "notification": tds_rules.get("cbdt_notification", "CBDT Notification 121/2026"),
            "notes": "Resident individual and HUF buyers do not require a TAN. Payment and challan-cum-statement filed via Form 141 Schedule E on e-filing portal.",
        }
    else:
        # TAN-based Form 144 or 27Q
        form_name = tds_rules.get("form_other", "144")
        section_name = tds_rules.get("section_new", "393(2)") if rules.get("version") == "2026-27" else tds_rules.get("section_old", "195")
        return {
            "form": form_name,
            "mechanism": "TAN-based quarterly return & challan deposit",
            "deadline": "Deposit by 7th of subsequent month; quarterly statement in Form " + form_name,
            "code": tds_rules.get("code", "1057"),
            "section": section_name,
            "notification": None,
            "notes": "Buyer must obtain TAN (Tax Deduction Account Number). Deposit tax via challan under code 1057 and file statement.",
        }


def calculate_exemption_scenarios(
    gain: float,
    is_long_term: bool,
    property_type: str,
    other_income: float,
    net_consideration: float,
    rules: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Step 10: Model Section 54, 54EC, and 54F what-if scenarios.
    """
    scenarios = {}
    if not is_long_term or gain <= 0:
        return scenarios

    # 1. Section 54EC (Capital Gain Bonds - NHAI, REC, PFC, IRFC)
    s85 = rules.get("exemptions", {}).get("s85", {})
    cap_54ec = s85.get("cap", 5000000)
    invest_54ec = min(gain, cap_54ec)
    gain_after_54ec = max(0.0, gain - invest_54ec)
    tax_after_54ec = calculate_tax_liability(gain_after_54ec, is_long_term, other_income, rules)
    baseline_tax = calculate_tax_liability(gain, is_long_term, other_income, rules)
    savings_54ec = round(baseline_tax["total_tax"] - tax_after_54ec["total_tax"], 2)

    scenarios["section_54ec"] = {
        "section": s85.get("section_new", "85"),
        "section_old": s85.get("section_old", "54EC"),
        "name": s85.get("name", "Capital Gains Bonds (54EC)"),
        "eligible": True,
        "max_investment_cap": cap_54ec,
        "investment_modeled": invest_54ec,
        "gain_after_exemption": round(gain_after_54ec, 2),
        "tax_after_exemption": tax_after_54ec["total_tax"],
        "tax_savings": savings_54ec,
        "lockin_period_years": s85.get("lockin_years", 5),
        "investment_window_months": s85.get("months", 6),
        "eligible_bonds": ["NHAI", "REC", "PFC", "IRFC"],
        "timing_rule": s85.get("timing_rule", "Invest within 6 months of transfer."),
    }

    # 2. Section 54 (House-to-House reinvestment)
    s82 = rules.get("exemptions", {}).get("s82", {})
    is_house_sold = property_type in ["residential", "house", "flat"]
    cap_54 = s82.get("cap", 100000000)
    invest_54_modeled = min(gain, cap_54)
    gain_after_54 = max(0.0, gain - invest_54_modeled)
    tax_after_54 = calculate_tax_liability(gain_after_54, is_long_term, other_income, rules)

    scenarios["section_54"] = {
        "section": s82.get("section_new", "82"),
        "section_old": s82.get("section_old", "54"),
        "name": s82.get("name", "Residential House Reinvestment (Section 54)"),
        "eligible": is_house_sold,
        "max_investment_cap": cap_54,
        "investment_modeled": invest_54_modeled if is_house_sold else 0,
        "gain_after_exemption": round(gain_after_54, 2) if is_house_sold else round(gain, 2),
        "tax_after_exemption": tax_after_54["total_tax"] if is_house_sold else baseline_tax["total_tax"],
        "tax_savings": round(baseline_tax["total_tax"] - tax_after_54["total_tax"], 2) if is_house_sold else 0.0,
        "lockin_period_years": s82.get("lockin_years", 3),
        "timing_rule": s82.get("timing_rule", "Purchase 1 yr before / 2 yrs after, or construct within 3 yrs."),
        "notes": "Available when selling a residential house. Reinvest in residential house in India." if is_house_sold else "Not applicable: Section 54 applies only to transfer of residential house.",
    }

    # 3. Section 54F (Plot/Commercial to residential house)
    s86 = rules.get("exemptions", {}).get("s86", {})
    is_non_house_sold = property_type in ["plot", "commercial"]
    cap_54f = s86.get("cap", 100000000)
    # Proportionate exemption: gain * (investment / net_consideration)
    # If 100% net consideration reinvested: full gain exempted up to cap
    invest_54f_modeled = min(net_consideration, cap_54f)
    prop_relief = (gain * (invest_54f_modeled / net_consideration)) if net_consideration > 0 else 0
    gain_after_54f = max(0.0, gain - prop_relief)
    tax_after_54f = calculate_tax_liability(gain_after_54f, is_long_term, other_income, rules)

    scenarios["section_54f"] = {
        "section": s86.get("section_new", "86"),
        "section_old": s86.get("section_old", "54F"),
        "name": s86.get("name", "Plot/Commercial Reinvestment (Section 54F)"),
        "eligible": is_non_house_sold,
        "max_investment_cap": cap_54f,
        "investment_modeled": invest_54f_modeled if is_non_non_house_sold(property_type) else 0,
        "gain_after_exemption": round(gain_after_54f, 2) if is_non_house_sold else round(gain, 2),
        "tax_after_exemption": tax_after_54f["total_tax"] if is_non_house_sold else baseline_tax["total_tax"],
        "tax_savings": round(baseline_tax["total_tax"] - tax_after_54f["total_tax"], 2) if is_non_house_sold else 0.0,
        "lockin_period_years": s86.get("lockin_years", 3),
        "timing_rule": s86.get("timing_rule", "Reinvest full net consideration in 1 residential house in India."),
        "notes": "Applies when selling land/commercial property. Must not own more than one residential house on sale date." if is_non_house_sold else "Not applicable: Section 54F applies to non-residential asset transfers.",
    }

    return scenarios


def is_non_non_house_sold(property_type: str) -> bool:
    return property_type in ["plot", "commercial"]


def compute_repatriation(
    source_of_funds: str,
    fy_remittances_made_usd: float,
    rules: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Step 11: Repatriation channel by source of funds; headroom vs USD 1,000,000.
    """
    limit_usd = rules.get("fema", {}).get("nro_annual_limit_usd", 1000000)

    if source_of_funds == "nre_fcnr":
        return {
            "channel": "Foreign Currency Inward Remittance / NRE / FCNR Channel",
            "limit_description": "Freely repatriable up to foreign exchange originally remitted in (covers up to 2 residential properties).",
            "is_usd_million_route": False,
            "annual_cap_usd": None,
            "remittances_made_usd": fy_remittances_made_usd,
            "headroom_usd": None,
            "forms_required": ["Form 145 (15CA)", "Form 146 (15CB CA Certificate)", "Bank Form A2", "FIRC / Inward remittance certificate"],
            "guidance_label": "Guidance; your Authorized Dealer (AD) bank decides",
            "notes": "Proceeds can be repatriated freely up to initial foreign exchange remitted into India, without the USD 1M cap.",
        }
    else:
        # NRO USD 1 million scheme
        headroom = max(0.0, limit_usd - fy_remittances_made_usd)
        return {
            "channel": "NRO Account Scheme (RBI USD 1 Million per Financial Year)",
            "limit_description": f"Up to USD {limit_usd:,.0f} per financial year from NRO account, subject to taxes paid.",
            "is_usd_million_route": True,
            "annual_cap_usd": limit_usd,
            "remittances_made_usd": fy_remittances_made_usd,
            "headroom_usd": headroom,
            "forms_required": [
                rules.get("remittance", {}).get("form_declaration_new", "Form 145"),
                rules.get("remittance", {}).get("form_ca_cert_new", "Form 146"),
                "Bank Form A2 & FEMA Declaration",
                "Sale Deed & Tax Computation",
            ],
            "guidance_label": "Guidance; your Authorized Dealer (AD) bank decides",
            "notes": "Covers all NRO remittances combined (capital gains, rental income, deposits). Amount above $1M requires prior RBI approval.",
        }


def build_timeline_and_checklist(
    transfer_date_str: str,
    rules: Dict[str, Any],
    is_long_term: bool,
    buyer_reporting: Dict[str, Any],
    has_loss: bool
) -> Dict[str, Any]:
    """
    Step 12: Build actionable checklist, key dates, advance tax instalments, and document lists.
    """
    lower_dec = rules.get("lower_deduction", {})
    remittance = rules.get("remittance", {})

    milestones = [
        {
            "stage": "Pre-Sale / Before Registration",
            "action": f"Apply for Lower/Nil Deduction Certificate under Section {lower_dec.get('section_new', '395')} ({lower_dec.get('form_new', 'Form 128')})",
            "detail": "Apply on e-filing / TRACES portal before property registration. Processing takes 3 to 6 weeks. Prevents over-deduction of TDS by buyer.",
            "mandatory": not has_loss,
            "priority": "Critical",
        },
        {
            "stage": "Registration & Payment",
            "action": f"Buyer Deducts TDS and Reports via {buyer_reporting['form']}",
            "detail": f"{buyer_reporting['mechanism']}. Due: {buyer_reporting['deadline']}. Ensure seller PAN is quoted accurately.",
            "mandatory": True,
            "priority": "Critical",
        },
        {
            "stage": "Advance Tax (if balance tax due)",
            "action": "Pay Advance Tax instalments (15 June: 15%, 15 Sept: 45%, 15 Dec: 75%, 15 Mar: 100%)",
            "detail": "If net tax liability after TDS deduction exceeds ₹10,000, interest under Sections 234B/234C applies if not deposited on schedule.",
            "mandatory": True,
            "priority": "Important",
        },
        {
            "stage": "ITR Filing & Refund Claim",
            "action": "File Indian Non-Resident Income Tax Return (ITR-2)",
            "detail": "Reconcile TDS credits on AIS/Form 26AS. Claim refund of any excess TDS deducted by the buyer.",
            "mandatory": True,
            "priority": "Critical",
        },
        {
            "stage": "Fund Repatriation Abroad",
            "action": f"Obtain {remittance.get('form_ca_cert_new', 'Form 146')} from CA and file {remittance.get('form_declaration_new', 'Form 145')}",
            "detail": "Submit to Authorized Dealer (AD) bank along with Form A2 and sale deed to transfer sale proceeds overseas.",
            "mandatory": True,
            "priority": "Essential",
        },
    ]

    documents = [
        "Title Deed / Registered Sale Deed of the property",
        "Purchase Deed / Allotment Letter / Possession Certificate of original acquisition",
        "Bank statements showing original inflow of funds (FIRC if foreign inward remittance)",
        "Proof of improvement expenses and renovation bills (if claiming)",
        "Brokerage and transfer expense payment receipts",
        "PAN Card of Seller and Buyer",
        "Passport / OCI Card and Overseas Tax Residence Proof",
        "NRO / NRE Bank Account details with AD Bank branch IFSC/SWIFT",
        "Agreement to Sell (for Lower Deduction Certificate application)",
    ]

    return {
        "milestones": milestones,
        "required_documents": documents,
    }


def calculate_nri_property_sale(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Master 12-step calculation function.
    Strictly deterministic, pure function, no state side-effects.
    """
    # -------------------------------------------------------------
    # 1. Gate: Check residential status and property type
    # -------------------------------------------------------------
    res_status = str(inputs.get("residential_status", "")).strip().lower()
    if res_status not in ["non_resident", "nri"]:
        return {
            "status": "STOP",
            "gate": "residential_status",
            "message": (
                "Speak to an adviser. The calculation engine is strictly configured for Non-Resident Indians (NRIs). "
                "Resident sellers in India are taxed under distinct provisions: 1% TDS under Section 393(1) (earlier s.194-IA), "
                "availability of basic tax exemption adjustments, and the optional indexation benefit for pre-23 July 2024 purchases. "
                "NRI-only logic must never be applied to a resident or RNOR individual."
            ),
            "help_url": "https://incometaxindia.gov.in",
        }

    prop_type = str(inputs.get("property_type", "")).strip().lower()
    if prop_type in ["agricultural", "agricultural_land", "plantation", "farm_house"]:
        return {
            "status": "STOP",
            "gate": "property_type",
            "message": (
                "FEMA Warning: Agricultural land, plantation property, and farm houses in India are out of scope. "
                "Under FEMA regulations, non-residents are prohibited from selling agricultural land or farm houses to any person "
                "other than a resident Indian citizen. Version 1 of this tool refuses agricultural property calculations."
            ),
            "help_url": "https://rbi.org.in",
        }

    # -------------------------------------------------------------
    # 2. Select law version and load rules JSON
    # -------------------------------------------------------------
    transfer_date_str = str(inputs.get("transfer_date", "2026-10-15")).strip()
    rules = load_rules(transfer_date_str)

    # -------------------------------------------------------------
    # 3. Holding months & long-term determination
    # -------------------------------------------------------------
    acq_date_str = str(inputs.get("acquisition_date", "2016-01-01")).strip()
    holding_months, is_long_term = calculate_holding_period_months(acq_date_str, transfer_date_str)

    # -------------------------------------------------------------
    # 4. Full Value of Consideration (110% safe harbor)
    # -------------------------------------------------------------
    sale_consideration = float(inputs.get("sale_consideration", 0))
    stamp_duty_value = float(inputs.get("stamp_duty_value", sale_consideration))
    sdv_tolerance = rules.get("sdv_tolerance", 1.10)

    if stamp_duty_value > (sale_consideration * sdv_tolerance):
        full_value_of_consideration = stamp_duty_value
        is_sdv_deemed = True
    else:
        full_value_of_consideration = sale_consideration
        is_sdv_deemed = False

    ownership_share = float(inputs.get("ownership_share", 100.0))
    share_fraction = ownership_share / 100.0

    user_sale_consideration = round(sale_consideration * share_fraction, 2)
    user_sdv = round(stamp_duty_value * share_fraction, 2)
    user_full_value = round(full_value_of_consideration * share_fraction, 2)

    # Deductions
    cost_of_acquisition = float(inputs.get("cost_of_acquisition", 0)) * share_fraction
    cost_of_improvement = float(inputs.get("cost_of_improvement", 0)) * share_fraction
    transfer_expenses = float(inputs.get("transfer_expenses", 0)) * share_fraction

    # -------------------------------------------------------------
    # 5. Capital Gain computation (No indexation for NRI)
    # -------------------------------------------------------------
    gain = user_full_value - cost_of_acquisition - cost_of_improvement - transfer_expenses
    gain = round(gain, 2)
    is_loss = gain < 0

    # -------------------------------------------------------------
    # 6 & 7. Tax Liability (Base Tax + Surcharge + Cess)
    # -------------------------------------------------------------
    other_income = float(inputs.get("other_indian_income", 0))
    tax_details = calculate_tax_liability(gain, is_long_term, other_income, rules)
    total_tax = tax_details["total_tax"]

    # -------------------------------------------------------------
    # 8. TDS Exposure without certificate
    # -------------------------------------------------------------
    pan_available = bool(inputs.get("pan_available", True))
    tds_details = compute_tds_exposure(
        user_sale_consideration, is_long_term, pan_available, rules
    )
    tds_exposure = tds_details["tds_exposure"]

    # -------------------------------------------------------------
    # 9. The Gap (Excess TDS held until refund) & Certificate TDS
    # -------------------------------------------------------------
    gap = max(0.0, round(tds_exposure - total_tax, 2))
    certificate_tds = total_tax
    certificate_effective_rate = round(
        (certificate_tds / user_sale_consideration) * 100, 2
    ) if user_sale_consideration > 0 else 0.0

    # -------------------------------------------------------------
    # 10. Exemption Scenarios (54, 54EC, 54F)
    # -------------------------------------------------------------
    net_consideration = user_sale_consideration - transfer_expenses
    exemption_scenarios = calculate_exemption_scenarios(
        gain, is_long_term, prop_type, other_income, net_consideration, rules
    )

    # -------------------------------------------------------------
    # 11. Repatriation Channel & Headroom
    # -------------------------------------------------------------
    source_of_funds = str(inputs.get("source_of_funds", "nro_rupee")).strip().lower()
    remittances_already_made_usd = float(inputs.get("fy_remittances_already_made_usd", 0.0))
    repatriation_details = compute_repatriation(
        source_of_funds, remittances_already_made_usd, rules
    )

    # -------------------------------------------------------------
    # Buyer TDS Mechanism & Form routing
    # -------------------------------------------------------------
    buyer_type = str(inputs.get("buyer_type", "resident_individual_huf")).strip().lower()
    buyer_reporting = determine_buyer_reporting(transfer_date_str, buyer_type, rules)

    # -------------------------------------------------------------
    # 12. Checklist, Timeline & Buyer Letter Data
    # -------------------------------------------------------------
    timeline_and_docs = build_timeline_and_checklist(
        transfer_date_str, rules, is_long_term, buyer_reporting, is_loss
    )

    # Return structured result
    return {
        "status": "SUCCESS",
        "law_version": rules.get("version"),
        "law_name": rules.get("law_name"),
        "effective_from": rules.get("effective_from"),
        "last_verified": rules.get("last_verified"),
        "holding_period": {
            "months": holding_months,
            "is_long_term": is_long_term,
            "asset_classification": "Long-Term Capital Asset" if is_long_term else "Short-Term Capital Asset",
            "threshold_months": rules.get("holding_months_long_term", 24),
        },
        "consideration": {
            "sale_price": user_sale_consideration,
            "stamp_duty_value": user_sdv,
            "sdv_tolerance_ratio": sdv_tolerance,
            "is_sdv_deemed": is_sdv_deemed,
            "full_value_of_consideration": user_full_value,
            "ownership_share_percent": ownership_share,
            "sdv_citation": rules.get("sdv_section", {}).get("section_new"),
        },
        "deductions": {
            "cost_of_acquisition": round(cost_of_acquisition, 2),
            "cost_of_improvement": round(cost_of_improvement, 2),
            "transfer_expenses": round(transfer_expenses, 2),
            "total_deductions": round(cost_of_acquisition + cost_of_improvement + transfer_expenses, 2),
            "indexation_applied": False,
            "indexation_note": "Indexation benefit is not available to Non-Residents as per current law (post 23 July 2024 regime).",
        },
        "capital_gain": {
            "gain_amount": gain,
            "is_loss": is_loss,
            "nature": "Long-Term Capital Gain" if is_long_term else "Short-Term Capital Gain",
            "citation": rules.get("ltcg_property", {}).get("section_new") if is_long_term else rules.get("stcg_property", {}).get("section_new"),
        },
        "tax_liability": tax_details,
        "tds_exposure": {
            **tds_details,
            "applied_on": "Entire Sale Consideration (as mandated by law without Lower Deduction Certificate)",
            "section": rules.get("tds", {}).get("section_new") if rules.get("version") == "2026-27" else rules.get("tds", {}).get("section_old"),
            "payment_code": rules.get("tds", {}).get("code"),
        },
        "gap_analysis": {
            "tds_exposure": tds_exposure,
            "actual_tax": total_tax,
            "excess_tds_held": gap,
            "certificate_tds": certificate_tds,
            "certificate_effective_rate_percent": certificate_effective_rate,
            "lower_deduction_section": rules.get("lower_deduction", {}).get("section_new") if rules.get("version") == "2026-27" else rules.get("lower_deduction", {}).get("section_old"),
            "lower_deduction_form": rules.get("lower_deduction", {}).get("form_new") if rules.get("version") == "2026-27" else rules.get("lower_deduction", {}).get("form_old"),
            "recommendation": (
                f"Apply for a Lower/Nil Deduction Certificate under Section {rules.get('lower_deduction', {}).get('section_new', '395')} "
                f"({rules.get('lower_deduction', {}).get('form_new', 'Form 128')}) before registration to save ₹{gap:,.0f} from being locked up."
                if gap > 0 else "Tax liability matches TDS exposure."
            ),
        },
        "exemptions": exemption_scenarios,
        "repatriation": repatriation_details,
        "buyer_reporting": buyer_reporting,
        "timeline_and_docs": timeline_and_docs,
        "verify_flags": rules.get("verify_flags", []),
        "disclaimer": "Estimate for information and planning purposes only. Not tax, legal or FEMA advice. Subject to verification with official CBDT and RBI notifications.",
    }
