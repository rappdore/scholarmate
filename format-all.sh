#!/bin/bash

# Manual formatting script for both frontend and backend

echo "🎨 Formatting all code..."

echo "📱 Formatting frontend code with Prettier..."
cd frontend
npm run format
cd ..

echo "🐍 Formatting backend code with Ruff..."
cd backend
uv run ruff format .
uv run ruff check --fix .
cd ..

echo "✅ All code formatted!"
