from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.architecture import router as architecture_router
from app.api.comparison import router as comparison_router
from app.api.documents import router as documents_router
from app.api.export import router as export_router
from app.api.queries import router as queries_router
from app.api.reports import router as reports_router
from app.api.validation import router as validation_router
from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.core.logging import configure_logging, get_logger
from app.core.schemas import HealthResponse, HealthStatus


settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("Starting AUTOSAR HLD Intelligence API")
    logger.info("Environment: %s", settings.app_env)
    yield
    logger.info("Shutting down AUTOSAR HLD Intelligence API")


app = FastAPI(
    title="AUTOSAR HLD Intelligence & Traceability Platform",
    description="Evidence-grounded AI platform for AUTOSAR HLD analysis.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(documents_router)
app.include_router(queries_router)
app.include_router(architecture_router)
app.include_router(validation_router)
app.include_router(comparison_router)
app.include_router(reports_router)
app.include_router(export_router)


@app.exception_handler(ApplicationError)
async def application_error_handler(request: Request, exc: ApplicationError):
    logger.error("[%s] %s", exc.code, exc.message)
    return JSONResponse(
        status_code=400,
        content={"error": exc.code, "message": exc.message},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled application exception")
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected internal server error occurred.",
        },
    )


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    return HealthResponse(
        status=HealthStatus.healthy,
        service="autosar-hld-intelligence-api",
        version="0.1.0",
    )


@app.get("/", tags=["System"])
async def root():
    return {
        "name": "AUTOSAR HLD Intelligence & Traceability Platform",
        "version": "0.1.0",
        "status": "running",
    }
