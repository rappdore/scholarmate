import logging
import sys
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

app = FastAPI(title="PDF AI Reader API", version="1.0.0")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    logger.info(f">>> Incoming request: {request.method} {request.url.path}")
    logger.info(f">>> Headers: {dict(request.headers)}")
    logger.info(f">>> Client: {request.client.host}:{request.client.port}")

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
        return JSONResponse(
            status_code=500, content={"detail": f"Internal server error: {str(e)}"}
        )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
