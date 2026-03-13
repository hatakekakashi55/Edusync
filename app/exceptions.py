"""
EduSync Backend - Custom Exception Handlers
Modularized from main.py
"""
import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException

logger = logging.getLogger("edusync")

async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom handler for HTTPExceptions"""
    logger.error(f"HTTP Error: {exc.detail} at {request.url}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status": "error"}
    )

async def general_exception_handler(request: Request, exc: Exception):
    """Custom handler for all unhandled exceptions"""
    logger.critical(f"Unhandled Exception: {str(exc)} at {request.url}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred. Our team has been notified.",
            "status": "error",
            "type": type(exc).__name__
        }
    )

def register_exception_handlers(app):
    """Register all exception handlers to the FastAPI app"""
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
