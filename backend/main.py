from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import ai, epub, highlights, notes, pdf

app = FastAPI(title="PDF AI Reader API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite default port
        "http://localhost:3000",  # React default port
        "http://127.0.0.1:5173",  # Alternative localhost
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def read_root():
    return {"message": "PDF AI Reader API", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Include routers
app.include_router(pdf.router)
app.include_router(epub.router)
app.include_router(ai.router)
app.include_router(notes.router)
app.include_router(highlights.router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
