import asyncio
from agents.code_agent import CodebaseAgent

async def run_fix():
    print("🔧 initializing Codebase Agent...")
    agent = CodebaseAgent(".")
    
    target_file = "/Users/yacinebenhamou/agY/static/styles.css"
    instruction = "Fix the header alignment (should be space-between) and remove the 45 degree rotation on the logo."
    
    print(f"🚑 Applying fix to: {target_file}")
    success = await agent.apply_fix(target_file, instruction)
    
    if success:
        print("✅ Fix applied successfully!")
    else:
        print("❌ Fix failed.")

if __name__ == "__main__":
    asyncio.run(run_fix())
