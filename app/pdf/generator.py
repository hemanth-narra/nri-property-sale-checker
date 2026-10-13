"""
Pure Python PDF Report Generator using ReportLab.
Generates comprehensive NRI Property Sale tax computation, exemption blueprint,
repatriation roadmap, and formal Buyer Instruction Letter in memory.
No system libraries needed - 100% portable on arm64 and x86_64.
"""

from datetime import datetime
import io
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def format_inr(amount: float) -> str:
    """Formats amount into Indian numbering representation."""
    if amount is None:
        return "₹ 0"
    is_neg = amount < 0
    s_amt = f"{abs(amount):.2f}"
    parts = s_amt.split(".")
    integer_part = parts[0]
    decimal_part = parts[1]

    if len(integer_part) <= 3:
        res = integer_part
    else:
        last3 = integer_part[-3:]
        rest = integer_part[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        res = ",".join(groups) + "," + last3

    prefix = "-₹ " if is_neg else "₹ "
    return prefix + res + ("" if decimal_part == "00" else f".{decimal_part}")


def generate_property_report_pdf(calc_result: Dict[str, Any], metadata: Dict[str, Any] = None) -> bytes:
    """
    Generates a formal multi-page PDF advisory report directly into memory bytes.
    """
    if metadata is None:
        metadata = {}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    primary_color = colors.HexColor("#121417")
    gold_color = colors.HexColor("#C59B27")
    text_dark = colors.HexColor("#1E293B")
    text_muted = colors.HexColor("#64748B")
    card_bg = colors.HexColor("#F8FAFC")
    border_color = colors.HexColor("#CBD5E1")

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=primary_color,
    )

    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=text_muted,
    )

    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=primary_color,
        spaceBefore=12,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=text_dark,
    )

    bold_body_style = ParagraphStyle(
        "BoldBody_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=13,
        textColor=text_dark,
    )

    callout_style = ParagraphStyle(
        "Callout_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#0F172A"),
    )

    story = []

    # ---------------------------------------------------------
    # HEADER BANNER
    # ---------------------------------------------------------
    header_table = Table(
        [
            [
                Paragraph("<b>NRI PROPERTY SALE CHECKER</b>", title_style),
                Paragraph(
                    f"<b>Law Position:</b> {calc_result.get('law_name', 'Income-tax Act, 2025')}<br/>"
                    f"<b>Rules Updated:</b> {calc_result.get('last_verified', '2026-10-10')}<br/>"
                    f"<b>Generated:</b> {datetime.now().strftime('%d %b %Y')}",
                    ParagraphStyle("MetaStyle", parent=body_style, fontSize=8, leading=11, alignment=2),
                ),
            ]
        ],
        colWidths=[4.2 * inch, 3.2 * inch],
    )
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(header_table)

    story.append(
        Paragraph(
            "Independent Capital Gains, Section 395/197 TDS Gap Analysis & Repatriation Blueprint",
            subtitle_style,
        )
    )
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=2, color=gold_color, spaceAfter=12))

    # ---------------------------------------------------------
    # EXECUTIVE SUMMARY & GAP HEADLINE (KEY HOOK)
    # ---------------------------------------------------------
    story.append(Paragraph("1. Executive Summary & TDS Exposure Gap", h1_style))

    gap_data = calc_result.get("gap_analysis", {})
    cap_data = calc_result.get("capital_gain", {})
    tax_data = calc_result.get("tax_liability", {})
    tds_data = calc_result.get("tds_exposure", {})
    cons_data = calc_result.get("consideration", {})

    excess_withheld = gap_data.get("excess_tds_held", 0)

    exec_rows = [
        [
            Paragraph("<b>Sale Consideration (User Share)</b>", body_style),
            Paragraph(format_inr(cons_data.get("sale_price", 0)), bold_body_style),
            Paragraph("<b>Capital Gain / (Loss)</b>", body_style),
            Paragraph(format_inr(cap_data.get("gain_amount", 0)), bold_body_style),
        ],
        [
            Paragraph("<b>Actual Tax Liability</b>", body_style),
            Paragraph(f"<font color='#0D9488'><b>{format_inr(tax_data.get('total_tax', 0))}</b></font>", bold_body_style),
            Paragraph("<b>TDS Deducted Without Certificate</b>", body_style),
            Paragraph(f"<font color='#E11D48'><b>{format_inr(tds_data.get('tds_exposure', 0))}</b></font>", bold_body_style),
        ],
        [
            Paragraph("<b>Excess TDS Locked Up (The Gap)</b>", body_style),
            Paragraph(f"<font color='#B45309'><b>{format_inr(excess_withheld)}</b></font>", bold_body_style),
            Paragraph("<b>Certificate TDS Rate</b>", body_style),
            Paragraph(f"<b>{gap_data.get('certificate_effective_rate_percent', 0)}% of price</b>", bold_body_style),
        ],
    ]

    summary_table = Table(exec_rows, colWidths=[2.2 * inch, 1.55 * inch, 2.2 * inch, 1.55 * inch])
    summary_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), card_bg),
            ("BOX", (0, 0), (-1, -1), 0.5, border_color),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(summary_table)
    story.append(Spacer(1, 10))

    # Alert Box for Gap
    if excess_withheld > 0:
        alert_content = [
            [
                Paragraph(
                    f"<b>CRITICAL ACTIONABLE SAVING:</b> Without a Lower Deduction Certificate, the buyer is required by law to withhold <b>{format_inr(tds_data.get('tds_exposure', 0))}</b> from the gross sale price. "
                    f"Your actual computed tax is only <b>{format_inr(tax_data.get('total_tax', 0))}</b>. "
                    f"Filing an application under <b>Section {gap_data.get('lower_deduction_section')} ({gap_data.get('lower_deduction_form')})</b> saves <b>{format_inr(excess_withheld)}</b> from being withheld and tied up until your tax refund.",
                    callout_style,
                )
            ]
        ]
        alert_table = Table(alert_content, colWidths=[7.4 * inch])
        alert_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF3C7")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#F59E0B")),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ])
        )
        story.append(alert_table)
        story.append(Spacer(1, 10))

    # ---------------------------------------------------------
    # LINE-BY-LINE TAX COMPUTATION
    # ---------------------------------------------------------
    story.append(Paragraph("2. Line-by-Line Computation with Citations", h1_style))

    ded_data = calc_result.get("deductions", {})
    hold_data = calc_result.get("holding_period", {})

    comp_rows = [
        [
            Paragraph("<b>Particulars</b>", bold_body_style),
            Paragraph("<b>Section / Rule Citation</b>", bold_body_style),
            Paragraph("<b>Amount (INR)</b>", bold_body_style),
        ],
        [
            Paragraph("Sale Consideration (Actual Agreement Value)", body_style),
            Paragraph("Gross agreed transfer price", subtitle_style),
            Paragraph(format_inr(cons_data.get("sale_price", 0)), body_style),
        ],
        [
            Paragraph("Stamp Duty Value (Circle / Guideline Rate)", body_style),
            Paragraph(f"110% tolerance test ({cons_data.get('sdv_citation', 's.50C')})", subtitle_style),
            Paragraph(format_inr(cons_data.get("stamp_duty_value", 0)), body_style),
        ],
        [
            Paragraph("<b>Full Value of Consideration</b> (Deemed under law)", body_style),
            Paragraph("Deemed value as per safe harbour check", subtitle_style),
            Paragraph(f"<b>{format_inr(cons_data.get('full_value_of_consideration', 0))}</b>", bold_body_style),
        ],
        [
            Paragraph("Less: Cost of Acquisition", body_style),
            Paragraph("Includes registration, stamp duty paid at purchase", subtitle_style),
            Paragraph(f"({format_inr(ded_data.get('cost_of_acquisition', 0))})", body_style),
        ],
        [
            Paragraph("Less: Cost of Improvement", body_style),
            Paragraph("Documented capital renovation expenditure", subtitle_style),
            Paragraph(f"({format_inr(ded_data.get('cost_of_improvement', 0))})", body_style),
        ],
        [
            Paragraph("Less: Transfer Expenses", body_style),
            Paragraph("Brokerage and legal expenses wholly connected", subtitle_style),
            Paragraph(f"({format_inr(ded_data.get('transfer_expenses', 0))})", body_style),
        ],
        [
            Paragraph(f"<b>Taxable {cap_data.get('nature')}</b>", bold_body_style),
            Paragraph(f"Holding: {hold_data.get('months')} months ({hold_data.get('asset_classification')})", subtitle_style),
            Paragraph(f"<b>{format_inr(cap_data.get('gain_amount', 0))}</b>", bold_body_style),
        ],
        [
            Paragraph("Base Tax Liability", body_style),
            Paragraph(f"Rate: {tax_data.get('tax_rate', 0)*100:.1f}% under {cap_data.get('citation')}", subtitle_style),
            Paragraph(format_inr(tax_data.get("base_tax", 0)), body_style),
        ],
        [
            Paragraph("Surcharge on Income", body_style),
            Paragraph(f"Surcharge rate {tax_data.get('surcharge_rate', 0)*100:.0f}% (LTCG cap 15%, marginal relief applied)", subtitle_style),
            Paragraph(format_inr(tax_data.get("surcharge", 0)), body_style),
        ],
        [
            Paragraph("Health & Education Cess", body_style),
            Paragraph("4% on Tax + Surcharge", subtitle_style),
            Paragraph(format_inr(tax_data.get("cess", 0)), body_style),
        ],
        [
            Paragraph("<b>Total Final Tax Liability</b>", bold_body_style),
            Paragraph("Net tax payable to Indian Government", subtitle_style),
            Paragraph(f"<font color='#0D9488'><b>{format_inr(tax_data.get('total_tax', 0))}</b></font>", bold_body_style),
        ],
    ]

    comp_table = Table(comp_rows, colWidths=[3.2 * inch, 2.5 * inch, 1.7 * inch])
    comp_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ("BOX", (0, 0), (-1, -1), 0.5, border_color),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ])
    )
    story.append(comp_table)
    story.append(Spacer(1, 10))

    # ---------------------------------------------------------
    # EXEMPTION SCENARIOS (WHAT-IF)
    # ---------------------------------------------------------
    story.append(Paragraph("3. Tax Exemption Opportunities (What-If Scenarios)", h1_style))

    exemptions = calc_result.get("exemptions", {})
    s54ec = exemptions.get("section_54ec", {})
    s54 = exemptions.get("section_54", {})
    s54f = exemptions.get("section_54f", {})

    ex_rows = [
        [
            Paragraph("<b>Exemption Section</b>", bold_body_style),
            Paragraph("<b>Reinvestment Option</b>", bold_body_style),
            Paragraph("<b>Lock-in & Deadlines</b>", bold_body_style),
            Paragraph("<b>Potential Tax Savings</b>", bold_body_style),
        ],
        [
            Paragraph(f"<b>{s54ec.get('section_old', '54EC')} / s.{s54ec.get('section', '85')}</b>", bold_body_style),
            Paragraph("Capital Gain Bonds (NHAI, REC, PFC, IRFC). Cap: ₹50 Lakhs", body_style),
            Paragraph("5 Years Lock-in.<br/>Invest within 6 months of sale.", subtitle_style),
            Paragraph(f"<font color='#0D9488'><b>{format_inr(s54ec.get('tax_savings', 0))}</b></font>", bold_body_style),
        ],
        [
            Paragraph(f"<b>{s54.get('section_old', '54')} / s.{s54.get('section', '82')}</b>", bold_body_style),
            Paragraph("Residential House Purchase / Construction. Cap: ₹10 Cr", body_style),
            Paragraph("3 Years Lock-in.<br/>Buy 1 yr before / 2 yrs after, or construct 3 yrs.", subtitle_style),
            Paragraph(f"<font color='#0D9488'><b>{format_inr(s54.get('tax_savings', 0))}</b></font>", bold_body_style),
        ],
        [
            Paragraph(f"<b>{s54f.get('section_old', '54F')} / s.{s54f.get('section', '86')}</b>", bold_body_style),
            Paragraph("Plot/Commercial Proceeds into Residential House", body_style),
            Paragraph("3 Years Lock-in.<br/>Reinvest full net consideration.", subtitle_style),
            Paragraph(f"<font color='#0D9488'><b>{format_inr(s54f.get('tax_savings', 0))}</b></font>", bold_body_style),
        ],
    ]

    ex_table = Table(ex_rows, colWidths=[1.6 * inch, 2.5 * inch, 1.8 * inch, 1.5 * inch])
    ex_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ("BOX", (0, 0), (-1, -1), 0.5, border_color),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ])
    )
    story.append(ex_table)
    story.append(Spacer(1, 10))

    # Page Break to Keep Clean Layout
    story.append(PageBreak())

    # ---------------------------------------------------------
    # FEMA REPATRIATION ROADMAP
    # ---------------------------------------------------------
    story.append(Paragraph("4. FEMA Repatriation Roadmap & Forex Outflow", h1_style))

    repat = calc_result.get("repatriation", {})
    headroom_text = (
        f"Available USD 1M Headroom for FY: <b>${repat.get('headroom_usd', 0):,.0f} USD</b>"
        if repat.get("is_usd_million_route")
        else "NRE / FCNR Inward Remittance Channel: Freely Repatriable up to original Foreign Inflow"
    )

    story.append(
        Paragraph(
            f"<b>Applicable Route:</b> {repat.get('channel')}<br/>"
            f"<b>RBI Policy:</b> {repat.get('limit_description')}<br/>"
            f"<b>Status:</b> {headroom_text}<br/>"
            f"<i>{repat.get('guidance_label')}</i>",
            body_style,
        )
    )
    story.append(Spacer(1, 8))

    repat_steps = [
        [
            Paragraph("<b>Form / Document</b>", bold_body_style),
            Paragraph("<b>Purpose & Issuing Authority</b>", bold_body_style),
        ],
        [
            Paragraph("<b>Form 146 (earlier 15CB)</b>", bold_body_style),
            Paragraph("Chartered Accountant Certificate certifying taxes paid on sale proceeds and compliance with FEMA.", body_style),
        ],
        [
            Paragraph("<b>Form 145 (earlier 15CA)</b>", bold_body_style),
            Paragraph("Online undertaking filed on Income Tax Portal by NRI prior to overseas transfer.", body_style),
        ],
        [
            Paragraph("<b>Form A2 & FEMA Declaration</b>", bold_body_style),
            Paragraph("Bank application form for outward forex remittance under Liberalised/NRO Scheme.", body_style),
        ],
        [
            Paragraph("<b>Sale Deed & Source Proofs</b>", bold_body_style),
            Paragraph("Registered transfer deed and bank statements proving funds were received in NRO account.", body_style),
        ],
    ]
    repat_table = Table(repat_steps, colWidths=[2.5 * inch, 4.9 * inch])
    repat_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ("BOX", (0, 0), (-1, -1), 0.5, border_color),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(repat_table)
    story.append(Spacer(1, 10))

    # ---------------------------------------------------------
    # BUYER INSTRUCTION LETTER (VALUABLE ARTIFACT)
    # ---------------------------------------------------------
    story.append(Paragraph("5. Formal Instructions for the Buyer (One-Page Letter)", h1_style))
    story.append(
        Paragraph(
            "Give this instruction letter to your buyer and their advocate to prevent disputes and avoid improper 1% or excess withholding at the registrar's office:",
            subtitle_style,
        )
    )
    story.append(Spacer(1, 6))

    buyer_rep = calc_result.get("buyer_reporting", {})
    letter_text = (
        f"<b>TO: THE PURCHASER / BUYER OF THE PROPERTY</b><br/><br/>"
        f"<b>RE: TDS DEDUCTION AND REPORTING ON PURCHASE FROM NON-RESIDENT INDIAN (NRI)</b><br/><br/>"
        f"Dear Sir / Madam,<br/><br/>"
        f"With reference to the agreed transfer of property, please note the statutory compliance required under the Indian Income-tax Act:<br/><br/>"
        f"1. <b>Status of Seller:</b> The seller is a Non-Resident Indian (NRI). Please note that the 1% TDS regime under Section 393(1) (earlier s.194-IA) applies exclusively to resident sellers and DOES NOT apply to this transaction.<br/>"
        f"2. <b>Statutory TDS Governing Section:</b> Section {buyer_rep.get('section')} under Payment Code {buyer_rep.get('code')}.<br/>"
        f"3. <b>Reporting Mechanism:</b> {buyer_rep.get('mechanism')}.<br/>"
        f"4. <b>Form to be filed:</b> <b>{buyer_rep.get('form')}</b>. "
        + (f"As per {buyer_rep.get('notification')}, resident individual and HUF buyers do not require a TAN (Tax Deduction Account Number) and may file directly using PAN.<br/>" if buyer_rep.get('notification') else "TAN is required for filing statement.<br/>")
        + f"5. <b>Statutory Filing Deadline:</b> {buyer_rep.get('deadline')}.<br/>"
        f"6. <b>Lower Deduction Certificate:</b> An application has been made under Section {gap_data.get('lower_deduction_section')} ({gap_data.get('lower_deduction_form')}). "
        f"Upon certificate issuance by the Assessing Officer, TDS must be deducted at the certified rate rather than the default statutory rate.<br/><br/>"
        f"Kindly furnish the Form {buyer_rep.get('form')} challan-cum-statement acknowledgement immediately after deposit so tax credits reflect on Form 26AS/AIS.<br/><br/>"
        f"Yours sincerely,<br/><b>Seller (Non-Resident Indian)</b>"
    )

    letter_box = Table([[Paragraph(letter_text, callout_style)]], colWidths=[7.4 * inch])
    letter_box.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 1, border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ])
    )
    story.append(letter_box)
    story.append(Spacer(1, 10))

    # ---------------------------------------------------------
    # TIMELINE & CONTACT INFO
    # ---------------------------------------------------------
    story.append(Paragraph("6. Advisory & CA Assistance", h1_style))
    contact_text = (
        "<b>Need assistance with Form 128 (Lower Deduction Certificate), Form 146 CA Certification, or ITR Filing?</b><br/>"
        "Prepared by: <b>Hemanth Kumar Narra</b> | ITR · GST · ROC · Trademarks · Startup Advisory<br/>"
        "Call / WhatsApp: <b>+91 8919712297</b> | Website: <b>hemanthnarra.in</b><br/>"
        "<i>Disclaimer: This document is an estimate and planning blueprint generated for informational purposes only. It does not constitute legal, tax, or FEMA opinion. Confirm specific cases with your Chartered Accountant prior to transaction closing.</i>"
    )
    contact_box = Table([[Paragraph(contact_text, callout_style)]], colWidths=[7.4 * inch])
    contact_box.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
            ("BOX", (0, 0), (-1, -1), 0.5, border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ])
    )
    story.append(contact_box)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
