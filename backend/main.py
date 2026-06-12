import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import (
    ai,
    epub,
    epub_highlights,
    epub_notes,
    epub_reading_statistics,
    highlights,
    llm_config,
    notes,
    pdf,
    reading_statistics,
    tts,
)
from app.services.registry import init_services

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Construct all shared services once, fail-fast, at startup (schema
    # init, cache build, thumbnail generation) instead of at import time.
    init_services()
    yield


app = FastAPI(title="PDF AI Reader API", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    logger.info(f">>> Incoming request: {request.method} {request.url.path}")

    try:
        response = await call_next(request)
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"<<< Response: {request.method} {request.url.path} - Status: {response.status_code} - Duration: {duration:.3f}s"
        )
        return response
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(
            f"!!! Request failed: {request.method} {request.url.path} - Duration: {duration:.3f}s - Error: {str(e)}",
            exc_info=True,
        )
        # Return a generic body to the client; details stay in the server log above
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )


# Localhost-only single-user app: allow the Vite dev server origins explicitly.
# "null" is included because the packaged Electron app loads the UI via file://,
# which browsers report as the "null" Origin (non-browser/file origins are not
# subject to CORS preflight the same way, but this keeps it explicit and safe).
# Nothing sends credentials, so allow_credentials stays False (wildcard or broad
# origins combined with allow_credentials=True is invalid/unsafe).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "null"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def read_root():
    logger.info("Root endpoint accessed")
    return {"message": "PDF AI Reader API", "status": "running"}


@app.get("/health")
async def health_check():
    logger.info("Health check endpoint accessed")
    return {"status": "healthy"}


# Include routers
app.include_router(pdf.router)
app.include_router(epub.router)
app.include_router(ai.router)
app.include_router(notes.router)
app.include_router(epub_notes.router)
app.include_router(highlights.router)
app.include_router(epub_highlights.router)
app.include_router(reading_statistics.router)
app.include_router(epub_reading_statistics.router)
app.include_router(llm_config.router)
app.include_router(tts.router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
