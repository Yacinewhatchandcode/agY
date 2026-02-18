#!/bin/bash

# 🧠 Local DeepSearch Setup Script
# This script automates the setup of a fully local DeepSearch system

set -e

echo "🚀 Starting Local DeepSearch Setup..."
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop and try again."
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama is not running. Starting Ollama..."
    echo "   Run 'ollama serve' in another terminal if this fails."
    echo ""
fi

# Pull required Ollama models
echo "🧠 Pulling required Ollama models..."
echo "   This may take a while depending on your internet connection..."
echo ""

models=("deepseek-r1:7b" "gemma2:2b" "nomic-embed-text")

for model in "${models[@]}"; do
    echo "📥 Pulling $model..."
    if ollama list | grep -q "$model"; then
        echo "   ✅ $model already exists"
    else
        ollama pull "$model"
        echo "   ✅ $model pulled successfully"
    fi
    echo ""
done

# Start Docker Compose stack
echo "🐳 Starting Docker Compose stack..."
docker compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check service health
echo ""
echo "🔍 Checking service health..."

if curl -s http://localhost:8080 > /dev/null 2>&1; then
    echo "   ✅ SearXNG is running on http://localhost:8080"
else
    echo "   ⚠️  SearXNG is starting... (may take a moment)"
fi

if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "   ✅ DeepSearch is running on http://localhost:3000"
else
    echo "   ⚠️  DeepSearch is starting... (may take a moment)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Local DeepSearch Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 Access your services:"
echo "   • DeepSearch UI:  http://localhost:3000"
echo "   • SearXNG:        http://localhost:8080"
echo ""
echo "📊 View logs:"
echo "   docker logs deepsearch -f"
echo "   docker logs searxng -f"
echo ""
echo "🛑 Stop services:"
echo "   docker compose down"
echo ""
echo "🔄 Restart services:"
echo "   docker compose restart"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
