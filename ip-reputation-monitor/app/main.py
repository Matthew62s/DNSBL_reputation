"""Main FastAPI application for IP Reputation Monitor."""

import logging
import sys
from contextlib import asynccontextmanager
from typing import Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.api.check import router as check_router
from app.api.targets import router as targets_router
from app.api.zones import router as zones_router
from app.api.monitor import router as monitor_router
from app.api.status import router as status_router
from app.api.metrics import router as metrics_router
from app.api.reports import router as reports_router
from app.core.config import settings
from app.core.database import init_db, get_db_context
from app.models.database import Target, Zone
from app.services.monitoring import get_monitoring_service
from app.services.reports import get_report_service

# Configure logging
def setup_logging():
    """Configure logging based on settings."""
    if settings.LOG_FORMAT == "json":
        from pythonjsonlogger import jsonlogger

        handler = logging.StreamHandler(sys.stdout)
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s",
            timestamp=True,
        )
        handler.setFormatter(formatter)
        logging.basicConfig(
            level=getattr(logging, settings.LOG_LEVEL.upper()),
            handlers=[handler],
        )
    else:
        logging.basicConfig(
            level=getattr(logging, settings.LOG_LEVEL.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    logger = logging.getLogger(__name__)
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

setup_logging()
logger = logging.getLogger(__name__)

# Setup rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create scheduler
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Initializing database...")
    init_db()

    # Initialize default zones if none exist
    with get_db_context() as db:
        zone_count = db.query(Zone).count()
        if zone_count == 0:
            logger.info("Initializing default DNSBL zones...")
            for zone_name in settings.DEFAULT_ZONES:
                is_spamhaus = zone_name in [z.lower() for z in settings.SPAMHAUS_ZONES]
                zone = Zone(
                    zone=zone_name,
                    description="Default DNSBL zone",
                    enabled=True,
                    is_spamhaus=is_spamhaus,
                )
                db.add(zone)
            db.commit()
            logger.info(f"Initialized {len(settings.DEFAULT_ZONES)} default zones")

    # Start scheduler
    if settings.SCHEDULER_ENABLED:
        logger.info("Starting scheduler...")
        scheduler.add_job(
            scheduled_monitoring,
            "interval",
            minutes=settings.SCHEDULER_INTERVAL_MINUTES,
            id="monitoring_job",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(f"Scheduler started (interval: {settings.SCHEDULER_INTERVAL_MINUTES} minutes)")

    logger.info("Application started successfully")
    yield

    # Shutdown
    logger.info("Shutting down...")
    if settings.SCHEDULER_ENABLED:
        scheduler.shutdown()
    logger.info("Application stopped")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="IP Reputation Monitor - DNSBL blacklist monitoring system",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="app/templates")


# Include API routers
app.include_router(check_router, prefix=settings.API_PREFIX)
app.include_router(targets_router, prefix=settings.API_PREFIX)
app.include_router(zones_router, prefix=settings.API_PREFIX)
app.include_router(monitor_router, prefix=settings.API_PREFIX)
app.include_router(status_router, prefix=settings.API_PREFIX)
app.include_router(metrics_router, prefix=settings.API_PREFIX)
app.include_router(reports_router, prefix=settings.API_PREFIX)


# ===== Web UI Routes =====

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard home page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/targets", response_class=HTMLResponse)
async def targets_page(request: Request):
    """Targets management page."""
    return templates.TemplateResponse("targets.html", {"request": request})


@app.get("/zones", response_class=HTMLResponse)
async def zones_page(request: Request):
    """Zones management page."""
    return templates.TemplateResponse("zones.html", {"request": request})


@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    """Reports page."""
    return templates.TemplateResponse("reports.html", {"request": request})


# ===== Scheduler Job =====

async def scheduled_monitoring():
    """Scheduled monitoring job."""
    logger.info("Running scheduled monitoring...")

    try:
        monitoring_service = get_monitoring_service()
        run = await monitoring_service.run_monitoring(triggered_by="scheduler")

        logger.info(
            f"Monitoring run {run.id} completed: "
            f"{run.listed_count} listed, {run.blocked_count} blocked, {run.error_count} errors"
        )

    except Exception as e:
        logger.error(f"Scheduled monitoring failed: {e}", exc_info=True)


# ===== Health Check =====

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


# ===== API Documentation Override =====

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Custom Swagger UI documentation."""
    from fastapi.openapi.docs import get_swagger_ui_html

    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{settings.APP_NAME} - API Documentation",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS,
    )
