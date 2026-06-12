from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import traceback

from app.config import get_settings
from app.logging_config import configure_logging
from app.api import health

settings = get_settings()

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api import health, discovery_jobs, websites

app.include_router(health.router, prefix=settings.API_PREFIX)
app.include_router(discovery_jobs.router, prefix=settings.API_PREFIX)
app.include_router(websites.router, prefix=settings.API_PREFIX)

from app.exceptions import ResourceNotFoundError, DuplicateResourceError, InvalidOperationError

@app.exception_handler(ResourceNotFoundError)
async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"error": "resource_not_found", "message": exc.message, "details": exc.details}
    )

@app.exception_handler(DuplicateResourceError)
async def duplicate_resource_handler(request: Request, exc: DuplicateResourceError):
    return JSONResponse(
        status_code=409,
        content={"error": "duplicate_resource", "message": exc.message, "details": exc.details}
    )

@app.exception_handler(InvalidOperationError)
async def invalid_operation_handler(request: Request, exc: InvalidOperationError):
    return JSONResponse(
        status_code=400,
        content={"error": "invalid_operation", "message": exc.message, "details": exc.details}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error occurred: {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal server error occurred."}
    )

@app.get("/")
def read_root():
    return {
        "message": settings.APP_NAME,
        "docs": "/docs",
        "health": f"{settings.API_PREFIX}/health"
    }
