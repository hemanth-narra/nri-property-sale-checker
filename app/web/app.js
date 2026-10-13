/**
 * NRI Property Sale Checker - Interactive Client Engine
 * Handles qualifier gates, dynamic calculations, locked paid preview,
 * PDF export, and buyer-side compliance calculations.
 */

// Global Application State
let currentCalcData = null;
let currentCalcResult = null;
let isReportUnlocked = false;

// Format Currency in Indian Rupees
function formatINR(amount) {
  if (amount === undefined || amount === null || isNaN(amount)) return "₹ 0";
  const isNeg = amount < 0;
  const absAmt = Math.abs(Math.round(amount));
  const s = absAmt.toString();
  let lastThree = s.substring(s.length - 3);
  const otherNumbers = s.substring(0, s.length - 3);
  if (otherNumbers !== '') {
    lastThree = ',' + lastThree;
  }
  const formatted = otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + lastThree;
  return (isNeg ? "-₹ " : "₹ ") + formatted;
}

// Convert INR to readable Lakh / Crore format
function formatWordsINR(amount) {
  const num = Math.abs(Number(amount));
  if (isNaN(num) || num === 0) return "₹ 0";
  if (num >= 10000000) {
    return `₹ ${(num / 10000000).toFixed(2)} Crore`;
  } else if (num >= 100000) {
    return `₹ ${(num / 100000).toFixed(2)} Lakh`;
  } else if (num >= 1000) {
    return `₹ ${(num / 1000).toFixed(1)} Thousand`;
  }
  return formatINR(num);
}

// Tab Switching
function switchMainTab(tabName) {
  document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

  const tabBtn = document.getElementById(`tab-btn-${tabName}`);
  const tabContent = document.getElementById(`tab-${tabName}-content`);
  if (tabBtn) tabBtn.classList.add('active');
  if (tabContent) tabContent.classList.add('active');

  if (tabName === 'buyer') {
    runBuyerChecker();
  }
}

// Flow Navigation
function startCheckFlow() {
  document.getElementById('hero-section').classList.add('hidden');
  const qSection = document.getElementById('qualifier-section');
  qSection.classList.remove('hidden');
  qSection.scrollIntoView({ behavior: 'smooth' });
  checkQualifierGates();
}

function loadWorkedExample() {
  // Sets worked example from Section 4.3 of blueprint
  document.getElementById('q-res-status').value = 'non_resident';
  document.getElementById('q-prop-type').value = 'residential';
  document.getElementById('q-transfer-date').value = '2026-10-15';
  document.getElementById('q-acq-mode').value = 'purchase';

  document.getElementById('inp-sale-price').value = '12000000';
  document.getElementById('inp-sdv').value = '12200000';
  document.getElementById('inp-acq-date').value = '2016-04-10';
  document.getElementById('inp-cost-acq').value = '6000000';
  document.getElementById('inp-cost-improv').value = '500000';
  document.getElementById('inp-expenses').value = '120000';
  document.getElementById('inp-ownership').value = '100';
  document.getElementById('inp-other-income').value = '0';
  document.getElementById('inp-pan-avail').value = 'true';
  document.getElementById('inp-buyer-type').value = 'resident_individual_huf';
  document.getElementById('inp-source-funds').value = 'nre_fcnr';
  document.getElementById('inp-fy-remittance-usd').value = '0';

  startCheckFlow();
  proceedToDetailsForm();
  executeFullCalculation();
}

// Qualifier Gate Logic (Step 1)
function checkQualifierGates() {
  const resStatus = document.getElementById('q-res-status').value;
  const propType = document.getElementById('q-prop-type').value;
  const stopAlert = document.getElementById('qualifier-stop-alert');
  const stopTitle = document.getElementById('stop-alert-title');
  const stopMsg = document.getElementById('stop-alert-message');
  const footerBtn = document.getElementById('qualifier-footer');

  if (resStatus !== 'non_resident') {
    stopAlert.classList.remove('hidden');
    stopTitle.innerText = "Residential Status Gate: Calculation Stopped";
    stopMsg.innerHTML = "<strong>Speak to an adviser.</strong> The calculation engine is strictly configured for Non-Resident Indians (NRIs). Under Indian tax law, resident sellers are governed by Section 393(1) (earlier Section 194-IA: 1% TDS on consideration above ₹50 lakh), can utilize basic tax exemption adjustments, and can opt for indexation on pre-23 July 2024 purchases. NRI rules must not be applied to a resident.";
    if (footerBtn) footerBtn.classList.add('hidden');
    return false;
  }

  if (propType === 'agricultural') {
    stopAlert.classList.remove('hidden');
    stopTitle.innerText = "FEMA Prohibition Gate: Out of Scope";
    stopMsg.innerHTML = "<strong>FEMA Warning:</strong> Under RBI regulations, Non-Residents (NRIs/OCIs) are strictly prohibited from selling agricultural land, plantation property, or farm houses to other non-residents. Agricultural property can only be sold to a resident Indian citizen, and requires specialized legal clearances. Version 1 of this tool refuses agricultural property calculations.";
    if (footerBtn) footerBtn.classList.add('hidden');
    return false;
  }

  // Eligible
  stopAlert.classList.add('hidden');
  if (footerBtn) footerBtn.classList.remove('hidden');
  return true;
}

function proceedToDetailsForm() {
  if (!checkQualifierGates()) return;
  document.getElementById('qualifier-section').classList.add('hidden');
  const dSection = document.getElementById('details-section');
  dSection.classList.remove('hidden');
  dSection.scrollIntoView({ behavior: 'smooth' });
  liveUpdateCalculations();
}

function editQualifier() {
  document.getElementById('details-section').classList.add('hidden');
  document.getElementById('qualifier-section').classList.remove('hidden');
}

// Live Update for Inputs & Real-time Validations
function liveUpdateCalculations() {
  const price = parseFloat(document.getElementById('inp-sale-price').value) || 0;
  const sdv = parseFloat(document.getElementById('inp-sdv').value) || price;

  // Words helper
  const wordsEl = document.getElementById('lbl-sale-price-words');
  if (wordsEl) wordsEl.innerText = formatWordsINR(price);

  // 110% safe harbour check
  const badge = document.getElementById('sdv-safeharbour-badge');
  if (badge) {
    if (sdv > price * 1.10) {
      badge.className = 'sdv-status-badge badge-red';
      badge.innerText = `Stamp Duty Exceeds 110% (Deemed Full Value: ${formatINR(sdv)})`;
    } else {
      badge.className = 'sdv-status-badge badge-green';
      badge.innerText = 'Within 110% Safe Harbour (No Deeming under s.50C)';
    }
  }

  // Holding period check
  const acqDate = document.getElementById('inp-acq-date').value;
  const trnDate = document.getElementById('q-transfer-date').value;
  const hpEl = document.getElementById('holding-period-indicator');
  if (acqDate && trnDate && hpEl) {
    const d1 = new Date(acqDate);
    const d2 = new Date(trnDate);
    let months = (d2.getFullYear() - d1.getFullYear()) * 12 + (d2.getMonth() - d1.getMonth());
    if (d2.getDate() < d1.getDate()) months--;
    months = Math.max(0, months);
    if (months > 24) {
      hpEl.innerHTML = `Holding: <strong>${months} months</strong> (Long-Term Capital Asset — 12.5% Tax Rate)`;
      hpEl.style.color = '#14b8a6';
    } else {
      hpEl.innerHTML = `Holding: <strong>${months} months</strong> (Short-Term Capital Asset — Taxed at Slab Rates)`;
      hpEl.style.color = '#f59e0b';
    }
  }

  // Source of funds remittance field visibility
  const sourceFunds = document.getElementById('inp-source-funds').value;
  const remWrap = document.getElementById('wrap-remittance-usd');
  if (remWrap) {
    if (sourceFunds === 'nre_fcnr') {
      remWrap.classList.add('hidden');
    } else {
      remWrap.classList.remove('hidden');
    }
  }
}

function resetDefaults() {
  document.getElementById('inp-sale-price').value = '12000000';
  document.getElementById('inp-sdv').value = '12200000';
  document.getElementById('inp-cost-acq').value = '6000000';
  document.getElementById('inp-cost-improv').value = '500000';
  document.getElementById('inp-expenses').value = '120000';
  liveUpdateCalculations();
}

// Master API Execution
async function executeFullCalculation() {
  const payload = {
    residential_status: document.getElementById('q-res-status').value,
    property_type: document.getElementById('q-prop-type').value,
    transfer_date: document.getElementById('q-transfer-date').value,
    acquisition_date: document.getElementById('inp-acq-date').value,
    mode_of_acquisition: document.getElementById('q-acq-mode').value,
    sale_consideration: parseFloat(document.getElementById('inp-sale-price').value) || 0,
    stamp_duty_value: parseFloat(document.getElementById('inp-sdv').value) || 0,
    cost_of_acquisition: parseFloat(document.getElementById('inp-cost-acq').value) || 0,
    cost_of_improvement: parseFloat(document.getElementById('inp-cost-improv').value) || 0,
    transfer_expenses: parseFloat(document.getElementById('inp-expenses').value) || 0,
    ownership_share: parseFloat(document.getElementById('inp-ownership').value) || 100,
    other_indian_income: parseFloat(document.getElementById('inp-other-income').value) || 0,
    pan_available: document.getElementById('inp-pan-avail').value === 'true',
    buyer_type: document.getElementById('inp-buyer-type').value,
    source_of_funds: document.getElementById('inp-source-funds').value,
    fy_remittances_already_made_usd: parseFloat(document.getElementById('inp-fy-remittance-usd').value) || 0,
  };

  currentCalcData = payload;

  try {
    const response = await fetch('/api/calc', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error("Calculation API call failed");
    }

    const data = await response.json();
    currentCalcResult = data;
    renderResults(data);
  } catch (err) {
    console.error("Error executing calculation:", err);
    alert("An error occurred during calculation. Please check your inputs.");
  }
}

// Render Results View
function renderResults(res) {
  if (res.status === 'STOP') {
    alert(res.message);
    return;
  }

  const resultsSection = document.getElementById('results-section');
  resultsSection.classList.remove('hidden');
  resultsSection.scrollIntoView({ behavior: 'smooth' });

  // 1. Top Gap Banner
  const gapData = res.gap_analysis || {};
  const gapAmt = gapData.excess_tds_held || 0;
  document.getElementById('res-gap-amount').innerText = formatINR(gapAmt);
  const tdsAmt = res.tds_exposure.tds_exposure;
  const taxAmt = res.tax_liability.total_tax;
  document.getElementById('res-gap-explanation').innerHTML = `
    The buyer is legally required to withhold <strong>${formatINR(tdsAmt)}</strong> unless you provide a Lower Deduction Certificate. 
    Your actual computed tax is only <strong>${formatINR(taxAmt)}</strong>. 
    Applying under <strong>Section ${gapData.lower_deduction_section} (${gapData.lower_deduction_form})</strong> protects <strong>${formatINR(gapAmt)}</strong> from remaining locked with the IT Department until your return refund.
  `;

  // 2. Metric Cards
  const gainData = res.capital_gain || {};
  document.getElementById('res-gain-value').innerText = formatINR(gainData.gain_amount);
  document.getElementById('res-gain-nature').innerText = gainData.nature;
  document.getElementById('res-gain-sub').innerText = `Full Value: ${formatINR(res.consideration.full_value_of_consideration)} - Deductions: ${formatINR(res.deductions.total_deductions)}`;

  const taxData = res.tax_liability || {};
  document.getElementById('res-tax-value').innerText = formatINR(taxData.total_tax);
  document.getElementById('res-tax-effective-rate').innerText = `${taxData.effective_tax_rate}% Effective`;
  document.getElementById('res-tax-sub').innerText = `Base: ${formatINR(taxData.base_tax)} + Surcharge: ${formatINR(taxData.surcharge)} + Cess: ${formatINR(taxData.cess)}`;

  const tdsData = res.tds_exposure || {};
  document.getElementById('res-tds-value').innerText = formatINR(tdsData.tds_exposure);
  document.getElementById('res-tds-rate').innerText = `${tdsData.effective_rate_percent}% on Gross Price`;
  document.getElementById('res-tds-sub').innerText = `Withheld on gross consideration of ${formatINR(res.consideration.sale_price)}`;

  document.getElementById('res-cert-rate').innerText = `${gapData.certificate_effective_rate_percent}%`;
  document.getElementById('res-cert-form-badge').innerText = `${gapData.lower_deduction_form} / s.${gapData.lower_deduction_section}`;
  document.getElementById('res-cert-sub').innerText = `Target withholding matches true tax: ${formatINR(taxData.total_tax)}`;

  // 3. Buyer Route Details
  const bRep = res.buyer_reporting || {};
  document.getElementById('res-buyer-form-name').innerText = bRep.form;
  document.getElementById('route-mechanism').innerText = bRep.mechanism;
  document.getElementById('route-form').innerText = bRep.form + (bRep.notification ? ` (${bRep.notification})` : '');
  document.getElementById('route-deadline').innerText = bRep.deadline;
  document.getElementById('route-code').innerText = `Code ${bRep.code} (Section ${bRep.section})`;

  // 4. FEMA Repatriation
  const repat = res.repatriation || {};
  document.getElementById('fema-channel-name').innerText = repat.channel;
  const fillEl = document.getElementById('headroom-progress-fill');
  const balEl = document.getElementById('headroom-balance-lbl');

  if (repat.is_usd_million_route) {
    const remMade = repat.remittances_made_usd || 0;
    const headroom = repat.headroom_usd || 0;
    const pct = Math.min(100, Math.round((remMade / 1000000) * 100));
    fillEl.style.width = `${pct}%`;
    balEl.innerHTML = `Available Headroom: <strong>$${headroom.toLocaleString()} USD</strong>`;
    document.getElementById('fema-notes-text').innerText = `Sale proceeds credit to NRO account. You have $${headroom.toLocaleString()} USD remaining in your annual $1M entitlement for this financial year (subject to Form 145/146 CA certification).`;
  } else {
    fillEl.style.width = '100%';
    balEl.innerHTML = `Route: <strong>Freely Repatriable Inward Remittance</strong>`;
    document.getElementById('fema-notes-text').innerText = "Foreign inward remittance funds are repatriable abroad up to the original foreign currency remitted into India, outside the USD 1 Million NRO cap.";
  }

  // 5. Legal Citations Panel
  document.getElementById('assumptions-law-title').innerText = res.law_name;
  const citGrid = document.getElementById('citation-grid');
  citGrid.innerHTML = `
    <div class="citation-pill">
      <strong>LTCG Property Rate</strong>
      <span>${res.law_version === '2026-27' ? 'Section 197(1)(b) (2025 Act)' : 'Section 112 (1961 Act)'} · 12.5% Flat</span>
    </div>
    <div class="citation-pill">
      <strong>TDS on NRI Seller</strong>
      <span>${res.law_version === '2026-27' ? 'Section 393(2), Sl. 17 · Code 1057' : 'Section 195 (1961 Act)'}</span>
    </div>
    <div class="citation-pill">
      <strong>Lower Deduction Route</strong>
      <span>${res.law_version === '2026-27' ? 'Section 395 · Form 128' : 'Section 197 · Form 13'}</span>
    </div>
    <div class="citation-pill">
      <strong>Resident Buyer Filing</strong>
      <span>${bRep.form} · ${bRep.mechanism}</span>
    </div>
    <div class="citation-pill">
      <strong>Safe Harbour 110%</strong>
      <span>${res.consideration.sdv_citation} · 10% Circle Rate Tolerance</span>
    </div>
    <div class="citation-pill">
      <strong>Remittance & CA Cert</strong>
      <span>${res.law_version === '2026-27' ? 'Forms 145 & 146 (2025 Act)' : 'Forms 15CA & 15CB (1961 Act)'}</span>
    </div>
  `;

  // 6. Populate Unlocked Modules (Exemptions, Buyer Letter, Checklist)
  renderUnlockedSections(res);
}

// Render Unlocked Report Data
function renderUnlockedSections(res) {
  // 1. Exemption Table
  const exTableBody = document.getElementById('exemptions-table-body');
  exTableBody.innerHTML = '';
  const exemptions = res.exemptions || {};

  for (const [key, ex] of Object.entries(exemptions)) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${ex.section_old} / s.${ex.section}</strong></td>
      <td>${ex.name}</td>
      <td>${formatINR(ex.max_investment_cap)}</td>
      <td>${ex.timing_rule}<br/><small>${ex.lockin_period_years} Years Lock-in</small></td>
      <td><strong>${formatINR(ex.investment_modeled)}</strong></td>
      <td>${formatINR(ex.tax_after_exemption)}</td>
      <td><strong style="color: #14b8a6;">${formatINR(ex.tax_savings)}</strong></td>
    `;
    exTableBody.appendChild(tr);
  }

  // 2. Buyer Instruction Letter
  const bRep = res.buyer_reporting || {};
  const gapData = res.gap_analysis || {};
  const letterBox = document.getElementById('buyer-letter-box');
  const letterText = `
TO: THE PURCHASER / BUYER OF THE PROPERTY
RE: TDS COMPLIANCE INSTRUCTIONS ON PURCHASE OF IMMOVABLE PROPERTY FROM NRI SELLER

Dear Sir / Madam,

With reference to the agreed transfer of the property, please take note of the mandatory statutory provisions governing TDS deduction and deposit under the Indian Income-tax Act:

1. NON-RESIDENT STATUS:
   The seller is a Non-Resident Indian (NRI). Please note that Section 393(1) (earlier Section 194-IA: 1% TDS) applies STRICTLY to resident sellers and DOES NOT apply to this transaction. Deducting 1% on an NRI sale is invalid under law and attracts personal penalty on the buyer of 1% to 1.5% interest per month plus ₹200/day late fees.

2. STATUTORY TDS WITHHOLDING PROVISION:
   - Governing Provision: Section ${bRep.section} (Payment Code ${bRep.code})
   - Standard Statutory Withholding Rate: ${res.tds_exposure.effective_rate_percent}% (including applicable surcharge & cess) on the gross sale consideration.

3. LOWER DEDUCTION CERTIFICATE APPLICATION:
   - Application has been submitted under Section ${gapData.lower_deduction_section} (${gapData.lower_deduction_form}) to the Assessing Officer (International Taxation).
   - Once issued, the certificate determines the exact rate of TDS to be deducted: ${gapData.certificate_effective_rate_percent}%, rather than the standard statutory rate.

4. BUYER DEPOSIT & REPORTING PROCEDURE:
   - Form to be filed: ${bRep.form}
   - Filing Mechanism: ${bRep.mechanism}
   ${bRep.notification ? `- Note: Under ${bRep.notification}, resident individual and HUF buyers do NOT require a TAN. Payment and challan-cum-statement can be filed directly on PAN.` : '- TAN is required.'}
   - Statutory Filing Due Date: ${bRep.deadline}

5. CHALLAN FURNISHING:
   Kindly share the official Form ${bRep.form} challan acknowledgement within 7 days of payment so tax credits reflect accurately on the seller's AIS / Form 26AS.

Yours sincerely,
Seller (Non-Resident Indian)
Date: ${new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
`.trim();

  letterBox.innerText = letterText;

  // 3. Timeline Steps
  const tlSteps = document.getElementById('timeline-steps');
  tlSteps.innerHTML = '';
  const milestones = res.timeline_and_docs.milestones || [];
  milestones.forEach((m, idx) => {
    const div = document.createElement('div');
    div.className = 'tl-step';
    div.innerHTML = `
      <div class="tl-dot">📌</div>
      <div class="tl-body">
        <strong>${m.stage}: ${m.action}</strong>
        <p>${m.detail}</p>
      </div>
    `;
    tlSteps.appendChild(div);
  });

  // 4. Checklist
  const clGrid = document.getElementById('checklist-grid');
  clGrid.innerHTML = '';
  const docs = res.timeline_and_docs.required_documents || [];
  docs.forEach(doc => {
    const div = document.createElement('div');
    div.className = 'cl-item';
    div.innerHTML = `<span class="cl-check">✓</span> <span>${doc}</span>`;
    clGrid.appendChild(div);
  });
}

function scrollToCertificateRoadmap() {
  const el = document.getElementById('certificate-roadmap-card');
  if (el) {
    if (!isReportUnlocked) {
      instantDemoUnlock();
    }
    el.scrollIntoView({ behavior: 'smooth' });
  }
}

function toggleAssumptionsPanel() {
  const body = document.getElementById('assumptions-body');
  const icon = document.getElementById('assumptions-toggle-icon');
  if (body.classList.contains('hidden')) {
    body.classList.remove('hidden');
    icon.innerText = '▲';
  } else {
    body.classList.add('hidden');
    icon.innerText = '▼';
  }
}

// Payment Modal & Unlocking
function openPaymentModal() {
  document.getElementById('payment-modal').classList.remove('hidden');
}

function closePaymentModal() {
  document.getElementById('payment-modal').classList.add('hidden');
}

async function submitSimulationPayment() {
  const email = document.getElementById('checkout-email').value || "user@example.com";
  try {
    const resp = await fetch('/webhooks/simulate-checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, tier: 'paid_report', amount: 12.0, currency: 'USD' })
    });
    if (resp.ok) {
      closePaymentModal();
      unlockReportView();
    }
  } catch (err) {
    console.error(err);
    alert("Could not process simulation payment.");
  }
}

function instantDemoUnlock() {
  unlockReportView();
}

function unlockReportView() {
  isReportUnlocked = true;
  document.getElementById('unlock-card').classList.add('hidden');
  const unlocked = document.getElementById('unlocked-content');
  unlocked.classList.remove('hidden');
  unlocked.scrollIntoView({ behavior: 'smooth' });
}

// PDF Download
async function downloadPdfReport() {
  if (!currentCalcResult) {
    alert("Please calculate results first.");
    return;
  }

  try {
    const resp = await fetch('/api/report/direct-download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        calc_data: currentCalcResult,
        email: "investor@example.com",
        order_id: "ORD_REPORT_DOWNLOAD"
      })
    });

    if (!resp.ok) throw new Error("PDF download failed");

    const blob = await resp.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `NRI_Property_Sale_Tax_Report_${new Date().toISOString().slice(0, 10)}.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();
  } catch (err) {
    console.error("PDF download error:", err);
    alert("Unable to generate PDF at this time.");
  }
}

// Copy Buyer Letter to Clipboard
function copyBuyerLetter() {
  const letterBox = document.getElementById('buyer-letter-box');
  if (!letterBox) return;
  navigator.clipboard.writeText(letterBox.innerText).then(() => {
    alert("Letter copied to clipboard! You can paste it directly into an email or document.");
  }).catch(() => {
    alert("Could not copy automatically. Please select the text and copy manually.");
  });
}

// Buyer-Side Checker Tool (Hook)
function runBuyerChecker() {
  const price = parseFloat(document.getElementById('bc-price').value) || 0;
  const transferDate = document.getElementById('bc-transfer-date').value || "2026-10-15";
  const entity = document.getElementById('bc-buyer-entity').value;
  const hasCert = document.getElementById('bc-has-cert').value === 'yes';
  const certRateWrap = document.getElementById('bc-cert-rate-wrap');

  if (hasCert) {
    certRateWrap.classList.remove('hidden');
  } else {
    certRateWrap.classList.add('hidden');
  }

  const isPostOct2026 = new Date(transferDate) >= new Date('2026-10-01');
  const isPostApr2026 = new Date(transferDate) >= new Date('2026-04-01');

  // Statutory rate: 12.5% + surcharge by price band + 4% cess
  let surchargeRate = 0.0;
  if (price > 10000000) surchargeRate = 0.15;
  else if (price > 5000000) surchargeRate = 0.10;

  const statEffectiveRate = 0.125 * (1 + surchargeRate) * 1.04;
  let effectiveRate = statEffectiveRate;
  let effectiveRatePercent = (statEffectiveRate * 100).toFixed(2);

  if (hasCert) {
    const customRate = parseFloat(document.getElementById('bc-cert-rate').value) || 6.41;
    effectiveRate = customRate / 100.0;
    effectiveRatePercent = customRate.toFixed(2);
  }

  const tdsAmount = Math.round(price * effectiveRate);

  // Form selection
  let formName = "Form 144 (TAN-based)";
  let tanRequired = true;
  let formNote = "Buyer must possess a TAN (Tax Deduction Account Number) and file quarterly TDS statement.";

  if (isPostOct2026 && entity === 'individual_huf') {
    formName = "Form 141 Schedule E (PAN-based)";
    tanRequired = false;
    formNote = "As per CBDT Notification 121/2026, resident individual and HUF buyers do NOT need a TAN. File directly using your PAN within 30 days from end of month.";
  } else if (!isPostApr2026) {
    formName = "Form 27Q (Section 195)";
  }

  const resDiv = document.getElementById('buyer-checker-result');
  resDiv.innerHTML = `
    <div class="buyer-result-box">
      <div class="flex-between mb-2">
        <div>
          <span class="step-badge">Buyer Obligation Summary</span>
          <h3 style="color: #ffffff; font-size: 20px;">Statutory TDS to Deduct: <span style="color: #f43f5e;">${formatINR(tdsAmount)}</span> (${effectiveRatePercent}%)</h3>
        </div>
        <span class="law-badge-sm">${formName}</span>
      </div>

      <div class="buyer-route-details">
        <div class="route-item">
          <strong>Applicable Section:</strong>
          <span>${isPostApr2026 ? 'Section 393(2), Sl. 17 (Code 1057)' : 'Section 195'}</span>
        </div>
        <div class="route-item">
          <strong>Filing Form:</strong>
          <span>${formName}</span>
        </div>
        <div class="route-item">
          <strong>Do You Need TAN?</strong>
          <span>${tanRequired ? 'YES (TAN Mandatory)' : 'NO (PAN-based filing allowed!)'}</span>
        </div>
        <div class="route-item">
          <strong>Deposit Due Date:</strong>
          <span>${isPostOct2026 && entity === 'individual_huf' ? 'Within 30 days from end of deduction month' : '7th of the following month'}</span>
        </div>
      </div>

      <div class="alert-box alert-danger mt-2">
        <div class="alert-icon">⚠️</div>
        <div class="alert-body">
          <strong>DO NOT DEDUCT 1% (OLD s.194-IA / s.393(1)):</strong> 
          Many property buyers mistakenly deduct 1% TDS under Section 194-IA. 
          The 1% rate applies strictly when the seller is a Resident Indian. 
          Because your seller is an NRI, deducting 1% will lead to income tax notices demanding short deduction interest and ₹200/day late penalty from you, the buyer!
        </div>
      </div>
    </div>
  `;
}

// Initial loader
document.addEventListener('DOMContentLoaded', () => {
  liveUpdateCalculations();
});
