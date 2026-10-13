# NRI Property Sale Checker

**A deterministic, no-LLM web application and calculation engine for Non-Resident Indians (NRIs) selling property in India.**

Compliant with the **Income-tax Act, 2025** (in force from 1 April 2026), **CBDT Notification 121/2026** (effective 1 October 2026), and backward-compatible with the **Income-tax Act, 1961**.

---

## 1. Key Value Proposition & The "Gap"

When an NRI sells immovable property in India, the buyer is required under **Section 393(2)** (formerly Section 195) to deduct TDS on the **entire sale consideration**, rather than the actual capital gain—unless the NRI seller obtains a **Lower/Nil Deduction Certificate** under **Section 395 (Form 128)**.

* **Worked Example:** On a ₹1.2 Crore sale with ₹53.8 Lakhs capital gain:
  * Statutory TDS without certificate: **₹ 17,94,000** (14.95% on gross price)
  * Actual Capital Gains Tax liability: **₹ 7,69,340** (12.5% LTCG + 10% Surcharge + 4% Cess)
  * **The Excess TDS Gap: ₹ 10,24,660** locked up until Indian ITR refund processing.

This tool calculates:
1. Exact capital gain and final tax liability.
2. The statutory TDS exposure and the exact refund gap.
3. Target lower-deduction certificate rate (Form 128 / s.395).
4. Section 54EC / 54 / 54F exemption scenarios (e.g. ₹50L into 54EC bonds drops tax to ₹49,400, saving ₹7.19 Lakhs).
5. FEMA Repatriation Channel & Headroom (USD 1 Million NRO limit vs freely repatriable NRE/FCNR foreign funds).
6. Ready-to-use 1-page Buyer Instruction Letter and Form 141 Schedule E compliance guide.

---

## 2. 2026 Law Concordance Map

| Subject | 1961 Act | 2025 Act / Rules 2026 | Key Feature |
| :--- | :--- | :--- | :--- |
| **NRI Property TDS** | Section 195 | **Section 393(2), Sl. 17 (Code 1057)** | Withheld on total gross consideration |
| **Lower Deduction Certificate** | Section 197 / Form 13 | **Section 395 / Form 128** | Applied on TRACES / e-filing portal |
| **Resident Buyer Filing** | Section 194-IA / Form 26QB | **Form 141 Schedule E** | **No TAN needed** for resident Ind/HUF (post 1 Oct 2026) |
| **Corporate/Other Buyer Filing** | Form 27Q | **Form 144 (Code 1057)** | TAN-based quarterly statement |
| **LTCG Property Flat Rate** | Section 112 | **Section 197(1)(b)** | 12.5% flat (No indexation for NRIs) |
| **Foreign Remittance / CA Cert**| Form 15CA / Form 15CB | **Form 145 / Form 146** | Chartered Accountant verification |
| **House-to-House Exemption** | Section 54 | **Section 82** | ₹10 Crore cap |
| **Bonds Exemption (54EC)** | Section 54EC | **Section 85** | ₹50 Lakh cap in REC/NHAI/PFC/IRFC |
| **110% Safe Harbour** | Section 50C | **Section 50C equivalent** | 10% Circle Rate tolerance before deemed value |

---

## 3. Architecture & Tech Stack

* **Language & Framework:** Python 3.12, FastAPI, Pydantic v2
* **Deterministic Engine:** Pure mathematical functions reading versioned JSON rules (`app/rules/2026-27.json` and `app/rules/1961.json`). **Zero hardcoded law constants.**
* **PDF Generator:** ReportLab (pure Python, 100% portable on ARM64 Linux and AMD64).
* **Database:** SQLite (`data/orders.db`) for orders and signed token access only.
* **Front-End:** Vanilla HTML, CSS, JavaScript (mobile-first, dark charcoal `#0d0f12` + gold `#d4af37` theme).
* **Privacy:** Strictly zero storage of property data or user tax inputs. Logs contain no inputs and no PAN.

---

## 4. Golden Test Suite

Run the full golden test suite verifying all calculation requirements from the Blueprint:

```bash
pytest tests/test_golden.py -v
```

All 9 golden cases pass:
* `test_golden_case_1`: ₹1.2 Cr sale -> Gain ₹53.8L, Tax ₹7,69,340, TDS ₹17,94,000, Gap ₹10,24,660.
* `test_golden_case_1_54ec_whatif`: ₹50L into 54EC bonds -> Tax ₹49,400, Saving ₹7,19,940.
* `test_golden_case_2_short_term`: 18 months holding -> STCG ₹9L taxed at slab rates, STCG verify flag raised.
* `test_golden_case_3_stamp_duty_deemed`: SDV ₹95L vs Price ₹80L (> 110%) -> Deemed full value ₹95L, Gain ₹45L, Tax ₹5,85,000, TDS ₹11,44,000.
* `test_golden_case_4_loss`: Loss scenario -> Tax ₹0, recommends nil-deduction certificate.
* `test_golden_case_5_law_versions`: 31 Mar 2026 (1961 Act) vs 1 Apr 2026 (2025 Act) switches legal citations and forms while retaining exact calculation logic.
* `test_golden_case_6_agricultural_land`: Agricultural property triggers FEMA prohibition stop.
* `test_golden_case_7_resident_stop`: Resident declaration triggers adviser stop.
* `test_golden_case_8_repatriation_headroom`: $700k remittances already made -> shows remaining $300k headroom under $1M scheme.

---

## 5. Local Setup & Running

### Requirements
* Python 3.12+

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run golden tests
pytest tests/ -v

# 3. Start local development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Open [http://localhost:8000](http://localhost:8000) in your web browser.

---

## 6. Deployment on Oracle Always Free ARM (Ampere A1)

Oracle Cloud Infrastructure (OCI) provides up to 4 Ampere A1 ARM cores and 24 GB RAM in their Always Free Tier.

### Step 1: Provision Oracle VM
1. Create a Compute Instance: **Ubuntu 22.04 or 24.04 (aarch64 / ARM)**.
2. Ensure VCN Ingress Rules allow ports **80** (HTTP) and **443** (HTTPS).

### Step 2: Install Docker & Docker Compose
```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

### Step 3: Clone Repository and Configure
```bash
git clone https://github.com/your-username/nri-property-sale-checker.git
cd nri-property-sale-checker

# Set up environment variables
cp .env.example .env
nano .env # update your secret keys
```

### Step 4: Configure Domain in Caddyfile
In `Caddyfile`, replace `:80` with your production domain name (e.g. `nri.hemanthnarra.in`):
```caddy
nri.hemanthnarra.in {
    reverse_proxy app:8000
    encode gzip zstd
}
```

### Step 5: Build and Run with Docker Compose
```bash
docker compose build
docker compose up -d
```

### Step 6: Verify Liveness
```bash
curl http://localhost:8000/healthz
# Returns: {"status": "ok", "service": "nri-property-sale-checker", "version": "1.0.0"}
```

---

## 7. API Reference

### `POST /api/calc`
Calculates capital gains, tax liability, TDS withholding, excess gap, exemption scenarios, and FEMA headroom in memory.
* Does not persist any property or financial data.

### `POST /api/report/direct-download`
Generates a formal multi-page ReportLab PDF in memory and streams it directly to the client.

### `GET /api/rules-meta?transfer_date=2026-10-15`
Returns legal provisions, active sections, and verification date stamps.

### `POST /webhooks/payment`
Receives payment confirmation from Merchant of Record (Paddle, Lemon Squeezy, Razorpay) and records order idempotently in SQLite.

### `GET /healthz`
Service health status probe.

---

## 8. Author & Advisory Contact

* **Blueprint & Lead Author:** Hemanth Kumar Narra
* **Expertise:** ITR · GST · ROC · Trademarks · Startup Advisory
* **Website:** [hemanthnarra.in](https://hemanthnarra.in)
* **Phone / WhatsApp:** +91 8919712297
