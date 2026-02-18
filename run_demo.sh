#!/bin/bash

echo "🚀 Visual Multi-Agent System Demo"
echo "=================================="
echo ""

# Check if Ollama is running
echo "📡 Checking Ollama service..."
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "❌ Ollama is not running. Please start it with: ollama serve"
    exit 1
fi
echo "✅ Ollama is running"
echo ""

# Check if vision model is available
echo "🔍 Checking for vision model..."
if ! ollama list | grep -q "llama3.2-vision"; then
    echo "⚠️  llama3.2-vision not found. Pulling model..."
    ollama pull llama3.2-vision
fi
echo "✅ Vision model ready"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip install -q langchain langchain-ollama langchain-community playwright pillow python-dotenv
echo "✅ Dependencies installed"
echo ""

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
playwright install chromium
echo "✅ Playwright ready"
echo ""

# Run the demo
echo "🎬 Running demo..."
echo ""
python app.py
