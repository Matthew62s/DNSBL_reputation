#!/bin/bash

# IP Reputation Monitor - Quick Start Script

set -e

echo "🚀 IP Reputation Monitor - Quick Start"
echo "======================================="
echo

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"
echo

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data reports
echo "✅ Directories created"
echo

# Build and start containers
echo "🐳 Building and starting containers..."
if docker compose version &> /dev/null; then
    docker compose up -d --build
else
    docker-compose up -d --build
fi
echo "✅ Containers started"
echo

# Wait for the application to be ready
echo "⏳ Waiting for application to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Application is ready!"
        break
    fi
    echo "   Waiting... ($i/30)"
    sleep 2
done

echo
echo "🎉 IP Reputation Monitor is running!"
echo
echo "📍 Access the web UI:"
echo "   http://localhost:8000"
echo
echo "📖 API Documentation:"
echo "   http://localhost:8000/docs"
echo
echo "🔧 Example API call:"
echo "   curl -X POST http://localhost:8000/api/check \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"ips\": [\"1.2.3.4\", \"8.8.8.8\"]}'"
echo
echo "📋 View logs:"
echo "   docker compose logs -f"
echo
echo "🛑 Stop the application:"
echo "   docker compose down"
echo
