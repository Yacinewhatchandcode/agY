# 🚀 Quick Start Guide

## ⚡ TL;DR

```bash
# 1. Start everything
./manage.sh start

# 2. Open browser
open http://localhost:3000

# 3. Start researching!
```

## 📋 Prerequisites Checklist

- [x] Docker Desktop installed and running
- [x] Ollama installed (`brew install ollama`)
- [x] Ollama models pulled:
  - `deepseek-r1:7b` (4.7 GB) - Smart reasoning
  - `gemma2:2b` (1.6 GB) - Fast planning
  - `nomic-embed-text` (274 MB) - Embeddings

## 🎯 First Time Setup

```bash
# Run the automated setup
./setup.sh
```

This will:
1. ✅ Check Docker & Ollama
2. ✅ Pull required models
3. ✅ Start Docker services
4. ✅ Verify health

## 🎮 Daily Usage

### Start Services
```bash
./manage.sh start
```

### Check Status
```bash
./manage.sh status
```

### View Logs
```bash
# DeepSearch logs
./manage.sh logs

# SearXNG logs
./manage.sh logs searxng
```

### Stop Services
```bash
./manage.sh stop
```

## 🧪 Testing Your Setup

### 1. Check SearXNG
```bash
curl http://localhost:8080
```
Should return HTML content.

### 2. Check DeepSearch
```bash
curl http://localhost:3000
```
Should return the UI.

### 3. Test Ollama
```bash
ollama list
```
Should show all three models.

## 🎨 Example Research Queries

Try these in the DeepSearch UI:

1. **Technical Deep Dive**
   ```
   What are the latest breakthroughs in local LLM inference optimization for Apple Silicon?
   ```

2. **Comparative Analysis**
   ```
   Compare the architecture and performance of DeepSeek-R1 vs GPT-4 for reasoning tasks
   ```

3. **How-To Research**
   ```
   How do I set up a production-ready RAG system using open-source tools?
   ```

4. **Current Events**
   ```
   What are the latest developments in AI regulation in the EU?
   ```

## 🔧 Troubleshooting

### Docker not running
```bash
open -a Docker
# Wait for Docker to start, then retry
```

### Port already in use
Edit `docker-compose.yml` and change ports:
```yaml
ports:
  - "3001:3000"  # DeepSearch
  - "8081:8080"  # SearXNG
```

### Models not found
```bash
ollama list
# If missing, pull them:
ollama pull deepseek-r1:7b
ollama pull gemma2:2b
```

### Service won't start
```bash
# Check logs
docker logs deepsearch
docker logs searxng

# Restart
./manage.sh restart
```

### Slow performance
- Ensure you're on Apple Silicon (M1/M2/M3/M4)
- Close other heavy applications
- Check Docker resource limits in Docker Desktop settings

## 📊 Resource Usage

Expected resource usage on M4 Max:

| Component | CPU | RAM | Disk |
|-----------|-----|-----|------|
| DeepSearch | 10-30% | 2-4 GB | - |
| SearXNG | 5-10% | 500 MB | - |
| Ollama (idle) | 0% | 100 MB | 6.5 GB |
| Ollama (active) | 50-100% | 8-16 GB | - |

## 🎯 Performance Tips

1. **Keep models loaded**: Run a test query to load models into memory
2. **Use Fast Model first**: Gemma2 handles initial planning quickly
3. **Limit search iterations**: Default is good, but you can adjust
4. **Close other apps**: Give Ollama maximum resources

## 🔐 Privacy Notes

✅ **Everything stays local:**
- No data sent to cloud services
- No API keys required
- No telemetry or tracking
- Web searches go through SearXNG (anonymized)

⚠️ **Web searches:**
- SearXNG queries external search engines (Google, DDG, etc.)
- These are anonymized and not linked to you
- No search history is stored externally

## 📈 Next Steps

Once you're comfortable with basic usage:

1. **Customize search engines** in SearXNG settings
2. **Adjust model parameters** in docker-compose.yml
3. **Add more models** for specialized tasks
4. **Integrate with other tools** (see README.md)

## 🆘 Getting Help

1. Check logs: `./manage.sh logs`
2. Verify status: `./manage.sh status`
3. Review README.md for detailed docs
4. Check Docker Desktop for container status

---

**Ready to research? Open http://localhost:3000 and start exploring!** 🚀
