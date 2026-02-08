run_backend:
	cd backend && uv run uvicorn main:app --reload

run_frontend:
	cd frontend && npm run dev

run_electron:
	cd frontend && npm run start

run_all:
	make run_backend & make run_frontend

# run_app launches electron which manages the backend automatically
run_app:
	cd frontend && npm run start

setup_hooks:
	./setup-hooks.sh

format_check:
	cd backend && uv run pre-commit run --all-files

format_backend:
	cd backend && uv run ruff format . && uv run ruff check --fix .

format_frontend:
	cd frontend && npm run format

typecheck_backend:
	git diff --name-only --diff-filter=ACM HEAD | grep '^backend/.*\.py$$' | sed 's|^backend/||' | xargs -r sh -c 'cd backend && uv run mypy "$$@"' sh || true

test_backend:
	cd backend && uv run pytest

test_frontend:
	cd frontend && npm run test

test_all:
	make test_backend && make test_frontend

clear_knowledge_db:
	sqlite3 backend/data/knowledge.db "DELETE FROM relationships; DELETE FROM concepts; DELETE FROM extraction_progress; DELETE FROM chunk_progress; DELETE FROM flashcards; VACUUM;"
