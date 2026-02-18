#!/bin/bash

# Quick commands for managing Local DeepSearch

case "$1" in
  start)
    echo "🚀 Starting Local DeepSearch..."
    docker compose up -d
    echo "✅ Services started!"
    echo "   DeepSearch: http://localhost:3000"
    echo "   SearXNG:    http://localhost:8080"
    ;;
  
  stop)
    echo "🛑 Stopping Local DeepSearch..."
    docker compose down
    echo "✅ Services stopped!"
    ;;
  
  restart)
    echo "🔄 Restarting Local DeepSearch..."
    docker compose restart
    echo "✅ Services restarted!"
    ;;
  
  logs)
    if [ -z "$2" ]; then
      echo "📊 Showing DeepSearch logs (Ctrl+C to exit)..."
      docker logs deepsearch -f
    else
      echo "📊 Showing $2 logs (Ctrl+C to exit)..."
      docker logs "$2" -f
    fi
    ;;
  
  status)
    echo "📊 Service Status:"
    echo ""
    docker compose ps
    echo ""
    echo "🌐 Endpoints:"
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
      echo "   ✅ DeepSearch: http://localhost:3000"
    else
      echo "   ❌ DeepSearch: http://localhost:3000 (not responding)"
    fi
    if curl -s http://localhost:8080 > /dev/null 2>&1; then
      echo "   ✅ SearXNG:    http://localhost:8080"
    else
      echo "   ❌ SearXNG:    http://localhost:8080 (not responding)"
    fi
    ;;
  
  update)
    echo "⬇️  Pulling latest images..."
    docker compose pull
    echo "🔄 Restarting services..."
    docker compose up -d
    echo "✅ Update complete!"
    ;;
  
  models)
    echo "🧠 Ollama Models:"
    ollama list
    ;;
  
  *)
    echo "🧠 Local DeepSearch Manager"
    echo ""
    echo "Usage: ./manage.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start      Start all services"
    echo "  stop       Stop all services"
    echo "  restart    Restart all services"
    echo "  logs       View DeepSearch logs (or 'logs searxng')"
    echo "  status     Check service status"
    echo "  update     Pull latest images and restart"
    echo "  models     List Ollama models"
    echo ""
    echo "Examples:"
    echo "  ./manage.sh start"
    echo "  ./manage.sh logs"
    echo "  ./manage.sh logs searxng"
    echo "  ./manage.sh status"
    ;;
esac
