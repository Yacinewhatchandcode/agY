import asyncio
import base64
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from agents.orchestrator import AutonomousOrchestrator
from app import VisualMultiAgent, execute_python, take_screenshot, web_browse


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting Antigravity Visual Agent Server...")
    yield
    # Shutdown
    print("🛑 Shutting down Antigravity Visual Agent Server...")


app = FastAPI(title="Antigravity Visual Agent Server", lifespan=lifespan)

# Initialize the agent
agent = VisualMultiAgent()

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def read_root():
    return FileResponse("static/index.html")


@app.get("/antigravity")
async def read_antigravity():
    # Both routes serve the same unified UI now
    return FileResponse("static/index.html")


@app.get("/health")
async def health_check():
    """Alias for /system/status"""
    return await system_status()


@app.get("/system/status")
async def system_status():
    """Health check and system status endpoint"""
    try:
        # Check if Ollama is accessible (basic health check)
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://localhost:11434/api/tags", timeout=2.0
                )
                ollama_status = "healthy" if response.status_code == 200 else "degraded"
        except:
            ollama_status = "unavailable"

        return JSONResponse(
            {
                "status": "healthy",
                "service": "antigravity-visual-agent",
                "timestamp": datetime.now().isoformat(),
                "components": {
                    "server": "healthy",
                    "ollama": ollama_status,
                    "agent": "initialized",
                },
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        )


@app.get("/api/models")
async def get_models():
    """Fetch available models from Ollama"""
    try:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://localhost:11434/api/tags", timeout=5.0
            )
            if response.status_code == 200:
                data = response.json()
                models = [
                    {
                        "name": model.get("name", model.get("model", "")),
                        "model": model.get("model", model.get("name", "")),
                        "size": model.get("size", 0),
                        "modified_at": model.get("modified_at", ""),
                        "details": model.get("details", {}),
                    }
                    for model in data.get("models", [])
                ]
                return JSONResponse({"models": models, "status": "success"})
            else:
                return JSONResponse(
                    status_code=503,
                    content={
                        "models": [],
                        "status": "error",
                        "error": f"Ollama returned status {response.status_code}",
                    },
                )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "models": [],
                "status": "error",
                "error": str(e),
            },
        )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🚀 WebSocket connection established")
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            action = message.get("action")

            print(f"📥 Received action: {action}")

            if action == "navigate":
                url = message.get("url")
                # Take screenshot and get info
                screenshot_path = "current_view.png"
                await take_screenshot(url, screenshot_path)

                with open(screenshot_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode("utf-8")

                await websocket.send_json(
                    {
                        "type": "navigation",
                        "data": {
                            "url": url,
                            "title": "Page Loaded",
                            "screenshot": img_data,
                            "timestamp": datetime.now().isoformat(),
                        },
                    }
                )

            elif action == "analyze":
                query = message.get("query")
                # Use the agent to analyze the current screenshot
                screenshot_path = "current_view.png"
                if os.path.exists(screenshot_path):
                    result = await agent.analyze_image(screenshot_path, query)
                    await websocket.send_json({"type": "analysis", "data": result})
                else:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "data": "No screenshot available to analyze. Please navigate first.",
                        }
                    )

            elif action == "screenshot":
                # Implementation can be more complex, but for demo:
                screenshot_path = "current_view.png"
                if os.path.exists(screenshot_path):
                    with open(screenshot_path, "rb") as f:
                        img_data = base64.b64encode(f.read()).decode("utf-8")
                    await websocket.send_json({"type": "screenshot", "data": img_data})

            elif action == "extract_dom":
                # Mock DOM extraction for now
                await websocket.send_json(
                    {
                        "type": "dom",
                        "data": {
                            "headings": [
                                {"level": "H1", "text": "Page Extraction Success"}
                            ],
                            "links": [{"text": "Example Link", "href": "#"}],
                            "images": [],
                            "forms": [],
                        },
                    }
                )

            elif action == "autonomous_task":
                goal = message.get("goal")
                repo_path = os.path.dirname(os.path.abspath(__file__))
                orchestrator = AutonomousOrchestrator(agent, repo_path=repo_path)

                # Setup thought callback to send WS messages live
                async def thought_callback(text, status="active"):
                    await websocket.send_json(
                        {"type": "analysis", "data": f"[Autonomous Agent] {text}"}
                    )
                    # Add pulse status
                    await websocket.send_json(
                        {
                            "type": "status",
                            "data": {"status": "Thinking...", "message": text},
                        }
                    )

                orchestrator.emit_step = thought_callback
                await orchestrator.run_task(goal)

    except WebSocketDisconnect:
        print("❌ WebSocket disconnected")
    except Exception as e:
        print(f"⚠️ Error: {e}")
        try:
            await websocket.send_json({"type": "error", "data": str(e)})
        except:
            pass


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8888)
