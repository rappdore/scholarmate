#!/bin/bash

# Setup script for pre-commit hooks
# This script sets up pre-commit hooks for both frontend and backend

echo "🔧 Setting up pre-commit hooks for the project..."

# Navigate to backend and install dependencies including pre-commit
echo "📦 Installing backend dependencies (including pre-commit)..."
cd backend
uv sync --group dev

# Install pre-commit hooks using the backend environment
echo "🪝 Installing pre-commit hooks..."
uv run pre-commit install

# Go back to root
cd ..

echo "✅ Pre-commit hooks setup complete!"
echo ""
echo "ℹ️  The hooks will now run automatically on git commit and will:"
echo "   - Format frontend files (JS/TS/CSS/etc.) with Prettier"
echo "   - Format and lint backend Python files with Ruff"
echo "   - Run general checks (trailing whitespace, large files, etc.)"
echo ""
echo "🧪 To test the hooks manually, run: cd backend && uv run pre-commit run --all-files"
