ScholarMate is an intelligent study assistant that transforms how you read and understand documents. Instead of opening PDFs or EPUBs in a traditional viewer, this application provides an interactive learning environment where an AI companion helps you comprehend complex content in real-time.

Frontend: React 19 + TypeScript + Vite, located in ./frontend

Backend: FastAPI + Python 3.12, located in ./backend

The backend uses a sqlite database. The database is stored at .backend/data/reading_progress.db

Backend uses uv for environment management. So use uv to run any python commands.


## Setup
- Backend: `cd backend && uv sync`
- Frontend: `cd frontend && npm install`

## Running
- Backend: `cd backend && uv run uvicorn app.main:app --reload`
- Frontend: `cd frontend && npm run dev`

But always ask before running.

## Code Quality
- Format backend: `make format_backend`
- Format frontend: `make format_frontend`
- Run both before committing

## Design
- in python use dict[str, Any] sparingly. Always prefer designing with types. Create types and pass data using properly types objects.
- When suggesting a design think through the potential pros and cons of the design especially cases where the design might fail. Edge cases are important. They force us to come back and redesign a more robust solution. Better to design a robust solution from the get go.
