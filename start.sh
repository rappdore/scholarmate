#!/bin/bash

# ScholarMate - Quick Start Script

echo "🚀 ScholarMate - Starting Application..."
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first:"
    echo "   https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is available
if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not available. Please install Docker Compose:"
    echo "   https://docs.docker.com/compose/install/"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo "❌ Docker daemon is not running. Please start Docker first."
    exit 1
fi

echo "✅ Docker is ready!"
echo ""

# Start the application
echo "🔧 Starting all services..."
echo "   This may take several minutes on first run (downloading AI models)"
echo ""

docker compose up -d

# Wait a moment for services to start
sleep 5

echo ""
echo "🎉 Application is starting up!"
echo ""
echo "📱 Access your application at:"
echo "   Frontend:  http://localhost:3000"
echo "   Backend:   http://localhost:8000"
echo "   API Docs:  http://localhost:8000/docs"
echo ""
echo "📊 Monitor the startup progress:"
echo "   docker compose logs -f"
echo ""
echo "🛑 To stop the application:"
echo "   docker compose down"
echo ""
echo "⚠️  Note: First startup may take 10-20 minutes to download AI models"
