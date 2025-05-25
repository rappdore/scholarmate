# Pre-commit Hooks Setup

This project uses pre-commit hooks to automatically format and lint code on commit for both the frontend and backend projects.

## Setup

To set up the pre-commit hooks, run:

```bash
make setup_hooks
# or
./setup-hooks.sh
```

This will:
1. Install pre-commit as a dev dependency in the backend project
2. Install the git pre-commit hooks
3. Configure hooks for both frontend and backend

## What the hooks do

When you commit code, the following will happen automatically:

### Frontend (JavaScript/TypeScript)
- **Prettier**: Formats all JS, TS, JSX, TSX, JSON, CSS, SCSS, MD, and HTML files in the `frontend/` directory
- Uses the configuration from `frontend/.prettierrc`

### Backend (Python)
- **Ruff**: Lints and fixes Python files in the `backend/` directory
- **Ruff Format**: Formats Python files according to the configuration in `backend/pyproject.toml`

### General
- Removes trailing whitespace
- Ensures files end with a newline
- Checks YAML syntax
- Prevents large files from being committed
- Checks for merge conflicts

## Manual formatting

You can also format code manually without committing:

```bash
# Format all code (frontend + backend)
./format-all.sh

# Format just backend
make format_backend

# Format just frontend
make format_frontend

# Run all pre-commit hooks manually
make format_check
```

## Configuration

- **Frontend**: Prettier configuration is in `frontend/.prettierrc`
- **Backend**: Ruff configuration is in `backend/pyproject.toml` under `[tool.ruff]`
- **Pre-commit**: Configuration is in `.pre-commit-config.yaml`

## Troubleshooting

If the hooks fail:
1. Fix the issues reported by the formatters/linters
2. Stage the fixed files: `git add .`
3. Commit again: `git commit -m "your message"`

To skip hooks temporarily (not recommended):
```bash
git commit --no-verify -m "your message"
```

To update pre-commit hooks:
```bash
cd backend && uv run pre-commit autoupdate
```
