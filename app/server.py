"""
NRI Property Sale Checker - Pure Python Server
Provides 100% pure-Python web server capability.
Ensures zero native DLL requirements on Windows host environments with strict Application Control policies,
while maintaining identical API surface to the FastAPI deployment in Docker.
"""

import io
import json
import logging
import os
from pathlib import Path
from bottle import Bottle, request, response, static_file, run

from app.engine.calculator import calculate_nri_property_sale, load_rules
from app.pdf.generator import generate_property_report_pdf
from app.db import init_db, save_order, get_order
from app.tokens import create_signed_token, verify_token


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("nri_server")

app = Bottle()
BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"


@app.hook('before_request')
def strip_trailing_slash():
    request.environ['PATH_INFO'] = request.environ['PATH_INFO'].rstrip('/')


@app.hook('after_request')
def enable_cors():
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'


@app.route('/healthz', method=['GET'])
def healthz():
    response.content_type = 'application/json'
    return json.dumps({
        "status": "ok",
        "service": "nri-property-sale-checker",
        "version": "1.0.0",
        "law_position": "Income-tax Act, 2025 (TY 2026-27) & Income-tax Act, 1961"
    })


@app.route('/api/rules-meta', method=['GET'])
def get_rules_meta():
    transfer_date = request.query.get('transfer_date', '2026-10-15')
    rules = load_rules(transfer_date)
    response.content_type = 'application/json'
    return json.dumps({
        "version": rules.get("version"),
        "law_name": rules.get("law_name"),
        "effective_from": rules.get("effective_from"),
        "last_verified": rules.get("last_verified"),
        "verify_flags": rules.get("verify_flags", []),
        "cbdt_notification": rules.get("tds", {}).get("cbdt_notification"),
        "ltcg_rate_percent": rules.get("ltcg_property", {}).get("rate", 0.125) * 100,
        "cess_percent": rules.get("cess", 0.04) * 100,
    })


@app.route('/api/calc', method=['POST'])
def api_calc():
    try:
        data = request.json or {}
    except Exception:
        data = {}

    result = calculate_nri_property_sale(data)
    response.content_type = 'application/json'
    return json.dumps(result)


@app.route('/api/report', method=['POST'])
def api_report():
    try:
        data = request.json or {}
    except Exception:
        data = {}

    order_id = data.get("order_id") or "ORD_DIRECT"
    email = data.get("email") or "customer@example.com"
    token = create_signed_token(order_id, email)

    response.content_type = 'application/json'
    return json.dumps({
        "status": "SUCCESS",
        "token": token,
        "download_url": f"/api/report/download/{token}",
        "expires_in_hours": 24,
        "order_id": order_id,
    })


@app.route('/api/report/direct-download', method=['POST'])
def api_report_direct_download():
    try:
        data = request.json or {}
    except Exception:
        data = {}

    calc_result = data.get("calc_data", {})
    if "tax_liability" not in calc_result:
        calc_result = calculate_nri_property_sale(calc_result)

    pdf_bytes = generate_property_report_pdf(calc_result, {"email": data.get("email")})

    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename="NRI_Property_Sale_Tax_Report.pdf"'
    return pdf_bytes


@app.route('/webhooks/payment', method=['POST'])
def api_webhook_payment():
    try:
        payload = request.json or {}
    except Exception:
        payload = {}

    order_id = payload.get("order_id") or "ORD_WEBHOOK"
    email = payload.get("email") or "buyer@example.com"
    save_order({
        "order_id": order_id,
        "email": email,
        "tier": payload.get("tier", "paid_report"),
        "amount": float(payload.get("amount", 12.0)),
        "currency": payload.get("currency", "USD"),
        "status": "completed",
    })
    response.content_type = 'application/json'
    return json.dumps({"status": "success", "order_id": order_id})


@app.route('/webhooks/simulate-checkout', method=['POST'])
def api_simulate_checkout():
    try:
        payload = request.json or {}
    except Exception:
        payload = {}

    order_id = payload.get("order_id") or "DEMO_ORDER"
    save_order({
        "order_id": order_id,
        "email": payload.get("email", "guest@example.com"),
        "tier": payload.get("tier", "paid_report"),
        "amount": float(payload.get("amount", 12.0)),
        "currency": payload.get("currency", "USD"),
        "status": "completed",
    })
    response.content_type = 'application/json'
    return json.dumps({"status": "success", "order_id": order_id})


@app.route('/static/<filename:path>')
def serve_static(filename):
    return static_file(filename, root=str(WEB_DIR))


@app.route('/')
def serve_index():
    return static_file('index.html', root=str(WEB_DIR))


def start_server(host='0.0.0.0', port=8000):
    init_db()
    logger.info(f"Starting server on http://{host}:{port}")
    run(app, host=host, port=port, quiet=False)


if __name__ == '__main__':
    start_server(host='127.0.0.1', port=8000)
