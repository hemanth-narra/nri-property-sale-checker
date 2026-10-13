"""
NRI Property Sale Checker - FastAPI Application Entrypoint
Serves REST API, webhooks, healthcheck, and static front-end.
"""

from contextlib import asynccontextmanager
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.api.calc import router as calc_router
from app.api.report import router as report_router
from app.api.webhooks import router as webhooks_router
from app.db import init_db


# Configure logging - strict privacy: NEVER log query params or request bodies containing property/tax inputs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nri_checker")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    init_db()
    logger.info("NRI Property Sale Checker initialized successfully.")
    yield


app = FastAPI(
    title="NRI Property Sale Checker",
    description="Deterministic capital gains, Section 395/197 TDS gap analysis, and FEMA repatriation engine.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(calc_router)
app.include_router(report_router)
app.include_router(webhooks_router)


@app.get("/healthz")
def healthcheck():
    """Liveness and readiness probe for Docker / Kubernetes / Uptime Kuma."""
    return {
        "status": "ok",
        "service": "nri-property-sale-checker",
        "version": "1.0.0",
        "law_position": "Income-tax Act, 2025 (TY 2026-27) & Income-tax Act, 1961",
    }


# Static web assets
WEB_DIR = Path(__file__).resolve().parent / "web"

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(WEB_DIR / "index.html")
