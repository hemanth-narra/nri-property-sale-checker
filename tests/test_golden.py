import pytest
from app.engine.calculator import calculate_nri_property_sale


def test_golden_case_1():
    """
    Case 1 (Worked example in Section 4.3):
    US NRI sells Hyderabad flat after 1 Oct 2026. Bought in 2016.
    Sale consideration: 1,20,00,000
    SDV: 1,22,00,000 (within 110% of 1.2 Cr = 1.32 Cr)
    Cost: 60,00,000
    Improvement: 5,00,000
    Expenses: 1,20,000
    Expected:
      Gain: 53,80,000
      Tax: 7,69,340
      TDS: 17,94,000
      Excess TDS: 10,24,660
    """
    inputs = {
        "residential_status": "non_resident",
        "property_type": "residential",
        "transfer_date": "2026-10-15",
        "acquisition_date": "2016-04-10",
        "sale_consideration": 12000000,
        "stamp_duty_value": 12200000,
        "cost_of_acquisition": 6000000,
        "cost_of_improvement": 500000,
        "transfer_expenses": 120000,
        "ownership_share": 100.0,
        "other_indian_income": 0,
        "pan_available": True,
        "buyer_type": "resident_individual_huf",
        "source_of_funds": "nre_fcnr",
    }
    result = calculate_nri_property_sale(inputs)
    assert result["status"] == "SUCCESS"
    assert result["capital_gain"]["gain_amount"] == 5380000.0
    assert result["tax_liability"]["total_tax"] == 769340.0
    assert result["tds_exposure"]["tds_exposure"] == 1794000.0
    assert result["gap_analysis"]["excess_tds_held"] == 1024660.0
    assert result["buyer_reporting"]["form"] == "141-ScheduleE"


def test_golden_case_1_54ec_whatif():
    """
    Scenario: ₹50 lakh into 54EC bonds.
    Taxable gain falls to ₹3,80,000.
    Tax = 47,500 + cess 1,900 = ₹49,400.
    Saving ≈ ₹7,19,940.
    """
    inputs = {
        "residential_status": "non_resident",
        "property_type": "residential",
        "transfer_date": "2026-10-15",
        "acquisition_date": "2016-04-10",
        "sale_consideration": 12000000,
        "stamp_duty_value": 12200000,
        "cost_of_acquisition": 6000000,
        "cost_of_improvement": 500000,
        "transfer_expenses": 120000,
        "ownership_share": 100.0,
    }
    result = calculate_nri_property_sale(inputs)
    s54ec = result["exemptions"]["section_54ec"]
    assert s54ec["eligible"] is True
    assert s54ec["gain_after_exemption"] == 380000.0
    assert s54ec["tax_after_exemption"] == 49400.0
    assert s54ec["tax_savings"] == 719940.0
    assert s54ec["lockin_period_years"] == 5
    assert s54ec["investment_window_months"] == 6


def test_golden_case_2_short_term():
    """
    Case 2:
    Held 18 months, price 90L, cost 80L, expenses 1L.
    Expected: Short-term gain 9,00,000 at slab; TDS about 30% of price plus surcharge and cess;
    show STCG verify flag.
    """
    inputs = {
        "residential_status": "non_resident",
        "property_type": "residential",
        "transfer_date": "2026-10-15",
        "acquisition_date": "2025-04-15",  # 18 months
        "sale_consideration": 9000000,
        "stamp_duty_value": 9000000,
        "cost_of_acquisition": 8000000,
        "cost_of_improvement": 0,
        "transfer_expenses": 100000,
    }
    result = calculate_nri_property_sale(inputs)
    assert result["status"] == "SUCCESS"
    assert result["holding_period"]["is_long_term"] is False
    assert result["capital_gain"]["gain_amount"] == 900000.0
    # 9L * 30% = 2,70,000 + 4% cess = 2,80,800
    assert result["tax_liability"]["total_tax"] == 280800.0
    # TDS on 90L with 30% slab rate + 10% surcharge (50L-1Cr) + 4% cess = 30% * 1.10 * 1.04 = 34.32%
    # 90,00,000 * 0.3432 = 30,88,800
    assert result["tds_exposure"]["effective_rate_percent"] == 34.32
    assert "stcg_slabs" in result["verify_flags"]


def test_golden_case_3_stamp_duty_deemed():
    """
    Case 3:
    Price 80L, SDV 95L, cost 50L (95 > 80 * 1.10 = 88)
    Expected: Full value 95L; gain 45L; tax 5,85,000 (no surcharge);
    TDS on 80L at 14.30% = 11,44,000.
    """
    inputs = {
        "residential_status": "non_resident",
        "property_type": "residential",
        "transfer_date": "2026-10-15",
        "acquisition_date": "2020-01-01",
        "sale_consideration": 8000000,
        "stamp_duty_value": 9500000,
        "cost_of_acquisition": 5000000,
        "cost_of_improvement": 0,
        "transfer_expenses": 0,
    }
    result = calculate_nri_property_sale(inputs)
    assert result["status"] == "SUCCESS"
    assert result["consideration"]["is_sdv_deemed"] is True
    assert result["consideration"]["full_value_of_consideration"] == 9500000.0
    assert result["capital_gain"]["gain_amount"] == 4500000.0
    # Tax: 45L * 12.5% = 5,62,500; Cess: 4% = 22,500; Total = 5,85,000 (<= 50L -> 0% surcharge)
    assert result["tax_liability"]["total_tax"] == 585000.0
    # TDS on consideration 80L: 10% surcharge, 12.5% * 1.10 * 1.04 = 14.30%
    # 80L * 14.30% = 11,44,000
    assert result["tds_exposure"]["tds_exposure"] == 1144000.0


def test_golden_case_4_loss():
    """
    Case 4:
    Price 40L, cost 60L -> Long-term loss; tax nil; TDS on 40L at 13% = 5,20,000;
    recommend nil-deduction certificate.
    """
    inputs = {
        "residential_status": "non_resident",
        "property_type": "residential",
        "transfer_date": "2026-10-15",
        "acquisition_date": "2020-01-01",
        "sale_consideration": 4000000,
        "stamp_duty_value": 4000000,
        "cost_of_acquisition": 6000000,
        "cost_of_improvement": 0,
        "transfer_expenses": 0,
    }
    result = calculate_nri_property_sale(inputs)
    assert result["status"] == "SUCCESS"
    assert result["capital_gain"]["is_loss"] is True
    assert result["capital_gain"]["gain_amount"] == -2000000.0
    assert result["tax_liability"]["total_tax"] == 0.0
    # TDS on 40L at 13% = 5,20,000
    assert result["tds_exposure"]["tds_exposure"] == 520000.0
    assert "Lower/Nil Deduction Certificate" in result["gap_analysis"]["recommendation"]


def test_golden_case_5_law_versions():
    """
    Case 5:
    Transfer on 31 Mar 2026 vs 1 Apr 2026.
    Law version, section numbers and forms switch; rates identical.
    """
    base_inputs = {
        "residential_status": "non_resident",
        "property_type": "residential",
        "acquisition_date": "2020-01-01",
        "sale_consideration": 10000000,
        "stamp_duty_value": 10000000,
        "cost_of_acquisition": 5000000,
    }

    # 31 Mar 2026 (1961 Act)
    inputs_old = {**base_inputs, "transfer_date": "2026-03-31"}
    res_old = calculate_nri_property_sale(inputs_old)

    # 1 Apr 2026 (2025 Act)
    inputs_new = {**base_inputs, "transfer_date": "2026-04-01"}
    res_new = calculate_nri_property_sale(inputs_new)

    assert res_old["law_version"] == "1961"
    assert res_new["law_version"] == "2026-27"
    assert res_old["tds_exposure"]["section"] == "195"
    assert "393(2)" in res_new["tds_exposure"]["section"]

    # Rates identical
    assert res_old["tax_liability"]["total_tax"] == res_new["tax_liability"]["total_tax"]
    assert res_old["tds_exposure"]["tds_exposure"] == res_new["tds_exposure"]["tds_exposure"]


def test_golden_case_6_agricultural_land():
    """
    Case 6:
    Agricultural land -> Out of scope; FEMA warning; no calculation.
    """
    inputs = {
        "residential_status": "non_resident",
        "property_type": "agricultural",
        "transfer_date": "2026-10-15",
        "sale_consideration": 5000000,
    }
    result = calculate_nri_property_sale(inputs)
    assert result["status"] == "STOP"
    assert result["gate"] == "property_type"
    assert "FEMA Warning" in result["message"]


def test_golden_case_7_resident_stop():
    """
    Case 7:
    Resident or RNOR self-declared -> Stop with adviser message.
    """
    inputs = {
        "residential_status": "resident",
        "property_type": "residential",
        "transfer_date": "2026-10-15",
    }
    result = calculate_nri_property_sale(inputs)
    assert result["status"] == "STOP"
    assert result["gate"] == "residential_status"
    assert "Speak to an adviser" in result["message"]


def test_golden_case_8_repatriation_headroom():
    """
    Case 8:
    NRO-route funds, FY remittances already USD 700k -> Headroom USD 300k shown.
    """
    inputs = {
        "residential_status": "non_resident",
        "property_type": "residential",
        "transfer_date": "2026-10-15",
        "acquisition_date": "2020-01-01",
        "sale_consideration": 10000000,
        "cost_of_acquisition": 5000000,
        "source_of_funds": "nro_rupee",
        "fy_remittances_already_made_usd": 700000.0,
    }
    result = calculate_nri_property_sale(inputs)
    assert result["status"] == "SUCCESS"
    assert result["repatriation"]["is_usd_million_route"] is True
    assert result["repatriation"]["headroom_usd"] == 300000.0
