ScholarMate is an intelligent study assistant that transforms how you read and understand documents. Instead of opening PDFs or EPUBs in a traditional viewer, this application provides an interactive learning environment where an AI companion helps you comprehend complex content in real-time.

Frontend: React 19 + TypeScript + Vite, located in ./frontend

Backend: FastAPI + Python 3.12, located in ./backend

The backend uses a sqlite database. The database is stored at .backend/data/reading_progress.db

Backend uses uv for environment management. So use uv to run any python commands.



- when asked to do something do not assume answers to questions that you do not know for sure. Use the AskUserQuestionTool aboute literally anything that you think will provide you more information on how to do the job better

- Always use the code simplifier agent at the end of coding session if we have added significant amount of code.

- Always make sure that we have testing coverage for any new lines of code added.

- Always mimic the directory structure of tests as they are in the source. Check the existing structure to understand it. For example, do not just put the test of example.py that is in src/utility/example.py in tests/unit/example.py. It should be in tests/unit/utility/test_example.py

- After any code change that is non-trivial run tests to see that nothing is failing

- once all tests pass run the formatters and linters and mypy. Look at the precommit hooks to see all the things that need to run before commit

- when making updates to a branch for code review comments, do not make a new branch. Update the same branch and add commits to it.



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
