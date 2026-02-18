# 📦 Local DeepSearch - Project Structure

## 📁 Files Overview

```
local-deepsearch/
├── docker-compose.yml    # Main Docker configuration
├── setup.sh             # Automated setup script
├── manage.sh            # Service management script
├── README.md            # Full documentation
├── QUICKSTART.md        # Quick start guide
└── COMPARISON.md        # vs Cloud services comparison
```

## 🎯 What Each File Does

### `docker-compose.yml`
**Purpose:** Defines the Docker stack (SearXNG + DeepSearch)

**Key Configuration:**
- SearXNG on port 8080 (meta search engine)
- DeepSearch on port 3000 (research UI)
- Connects to Ollama on host machine
- Uses 3 models: deepseek-r1:7b, gemma2:2b, nomic-embed-text

**When to edit:**
- Change ports if conflicts occur
- Modify model selection
- Adjust environment variables

### `setup.sh`
**Purpose:** One-time automated setup

**What it does:**
1. Checks Docker is running
2. Checks Ollama is available
3. Pulls required Ollama models
4. Starts Docker Compose stack
5. Verifies service health

**When to run:**
- First time setup
- After system reset
- To verify all dependencies

### `manage.sh`
**Purpose:** Daily service management

**Commands:**
```bash
./manage.sh start    # Start services
./manage.sh stop     # Stop services
./manage.sh restart  # Restart services
./manage.sh logs     # View logs
./manage.sh status   # Check health
./manage.sh update   # Update images
./manage.sh models   # List Ollama models
```

**When to use:**
- Daily start/stop operations
- Debugging (logs, status)
- Updating to latest versions

### `README.md`
**Purpose:** Complete documentation

**Sections:**
- Features overview
- Architecture diagram
- Installation instructions
- Usage guide
- Troubleshooting
- Comparison with Perplexity
- Optional upgrades

**When to read:**
- First time setup
- Troubleshooting issues
- Understanding architecture
- Planning upgrades

### `QUICKSTART.md`
**Purpose:** Fast reference guide

**Sections:**
- TL;DR commands
- Prerequisites checklist
- Daily usage patterns
- Example queries
- Common troubleshooting
- Performance tips

**When to use:**
- Quick command reference
- Daily operations
- Testing setup
- Performance optimization

### `COMPARISON.md`
**Purpose:** Detailed comparison analysis

**Sections:**
- Feature matrix vs cloud services
- Performance benchmarks
- Cost analysis (5-year savings)
- Privacy comparison
- Use case recommendations
- Real-world scenarios

**When to read:**
- Deciding between local vs cloud
- Justifying setup to others
- Understanding trade-offs
- Choosing right tool for task

## 🚀 Quick Command Reference

### First Time Setup
```bash
cd /Users/yacinebenhamou/agY/local-deepsearch
./setup.sh
```

### Daily Usage
```bash
# Start
./manage.sh start

# Use
open http://localhost:3000

# Stop
./manage.sh stop
```

### Troubleshooting
```bash
# Check status
./manage.sh status

# View logs
./manage.sh logs

# Restart
./manage.sh restart
```

## 🔧 Configuration Files

### Docker Compose Environment Variables

```yaml
OLLAMA_BASE_URL=http://host.docker.internal:11434
  # Points to Ollama on your Mac

SEARCH_API=searxng
  # Uses SearXNG for web search

SEARXNG_URL=http://searxng:8080
  # Internal Docker network URL

EMBEDDING_MODEL=nomic-embed-text
  # For semantic search

FAST_MODEL=gemma2:2b
  # Quick planning queries

SMART_MODEL=deepseek-r1:7b
  # Deep reasoning & synthesis
```

### Customization Options

**Change ports:**
```yaml
ports:
  - "3001:3000"  # DeepSearch
  - "8081:8080"  # SearXNG
```

**Change models:**
```yaml
FAST_MODEL=llama3.2:3b
SMART_MODEL=llama3.1:8b
```

**Add resource limits:**
```yaml
deploy:
  resources:
    limits:
      cpus: '4'
      memory: 8G
```

## 📊 Service Architecture

```
┌──────────────────────────────────────────────────┐
│                  Your Mac (M4 Max)               │
│                                                  │
│  ┌─────────────────────────────────────────┐   │
│  │         Ollama (Port 11434)             │   │
│  │  • deepseek-r1:7b                       │   │
│  │  • gemma2:2b                            │   │
│  │  • nomic-embed-text                     │   │
│  └───────────▲─────────────────────────────┘   │
│              │                                   │
│  ┌───────────┴─────────────────────────────┐   │
│  │      Docker Compose Stack               │   │
│  │                                          │   │
│  │  ┌────────────────────────────────┐    │   │
│  │  │  DeepSearch (Port 3000)        │    │   │
│  │  │  • Research Agent              │    │   │
│  │  │  • Query Planner               │    │   │
│  │  │  • Synthesizer                 │    │   │
│  │  └──────────▲─────────────────────┘    │   │
│  │             │                            │   │
│  │  ┌──────────┴─────────────────────┐    │   │
│  │  │  SearXNG (Port 8080)           │    │   │
│  │  │  • Google, DDG, Bing           │    │   │
│  │  │  • Anonymized search           │    │   │
│  │  └────────────────────────────────┘    │   │
│  └─────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
                       │
                       ▼
                  Internet
              (Web search only)
```

## 🎓 Learning Path

### Day 1: Setup & Basics
1. Read QUICKSTART.md
2. Run setup.sh
3. Try example queries
4. Learn manage.sh commands

### Day 2: Understanding
1. Read README.md
2. Explore architecture
3. Check logs to see how it works
4. Try different query types

### Day 3: Optimization
1. Read COMPARISON.md
2. Understand trade-offs
3. Customize for your needs
4. Optimize performance

### Week 2: Advanced
1. Experiment with different models
2. Adjust search parameters
3. Integrate with other tools
4. Consider upgrades (CLI, multi-agent, etc.)

## 🆘 Support Resources

### Quick Help
1. `./manage.sh status` - Check what's running
2. `./manage.sh logs` - See what's happening
3. QUICKSTART.md - Common solutions

### Deep Dive
1. README.md - Full documentation
2. Docker logs - Detailed debugging
3. Ollama logs - Model issues

### Decision Making
1. COMPARISON.md - Choose right tool
2. Use case recommendations
3. Cost/benefit analysis

---

**You're all set! Start with QUICKSTART.md and you'll be researching in minutes.** 🚀
