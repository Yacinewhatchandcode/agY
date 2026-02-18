import asyncio
import websockets
import json

async def trigger_healing():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        print("🔌 Connected to Nervous System...")
        
        # Send the goal
        goal = "The header layout is broken (items are bunched on the left) and the logo is rotated. Find the CSS and fix it."
        await websocket.send(json.dumps({
            "action": "autonomous_task",
            "goal": goal
        }))
        print(f"🎯 Goal Sent: {goal}\n")

        # Listen for thoughts
        while True:
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=60.0)
                data = json.loads(response)
                
                if data.get("type") == "analysis":
                    print(f"🧠 {data['data']}")
                    
                    # Simulate animation progress (replace with actual CSS animation)
                    current AnimationProgress: int = 10
                    await asyncio.sleep(2)  # Simulate processing time
                    
                    # Update progress bar and animation state
                    if data.get("progress"):
                        progress = data["progress"]
                        print(f"Progress: {int(progress)}%")
                        
                        # Update progress bar (replace with actual update)
                        display.progress.value = f"{int(progress)}%"
                    
                if "Reloading browser" in str(data):
                    print("\n✅ Fix applied and verification complete.")
                    break
            except asyncio.TimeoutError:
                print("⚠️ Timeout waiting for agent thought.")
                break

if __name__ == "__main__":
    asyncio.run(trigger_healing())