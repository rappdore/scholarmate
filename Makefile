run_backend:
	cd backend && uv run uvicorn main:app --reload

run_frontend:
	cd frontend && npm run dev

run_all:
	make run_backend & make run_frontend

setup_hooks:
	./setup-hooks.sh

format_check:
	cd backend && uv run pre-commit run --all-files

format_backend:
	cd backend && uv run ruff format . && uv run ruff check --fix .

format_frontend:
	cd frontend && npm run format
