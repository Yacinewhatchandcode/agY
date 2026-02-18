import asyncio
import sys
import os
sys.path.insert(0, os.getcwd())
from agents.product_agent import ProductAgent

async def test_planning_logic():
    print("🧪 Testing Product Agent Prompt Logic...")
    agent = ProductAgent()
    
    # Test Case 1: Generic Goal
    goal = "Test the login flow for the 'Production Studio' app."
    print(f"\nGoal: {goal}")
    
    plan = await agent.create_test_plan(goal)
    
    print("\n📋 Generated Plan:")
    bias_detected = False
    for step in plan:
        print(f" - {step['description']} -> {step['expected_outcome']}")
        if "Antigravity" in step['expected_outcome']:
            bias_detected = True
            
    if bias_detected:
        print("\n❌ FAILURE: 'Antigravity' bias detected in criteria!")
        sys.exit(1)
    else:
        print("\n✅ SUCCESS: No 'Antigravity' bias detected.")

    # Test Case 2: Specific Context
    goal2 = "Verify the 'SuperApp' dashboard."
    print(f"\nGoal: {goal2}")
    plan2 = await agent.create_test_plan(goal2)
    for step in plan2:
        print(f" - {step['description']} -> {step['expected_outcome']}")
        if "Antigravity" in step['expected_outcome']:
            print("\n❌ FAILURE: 'Antigravity' bias detected in criteria!")
            sys.exit(1)
            
    print("\n✅ All tests passed.")

if __name__ == "__main__":
    asyncio.run(test_planning_logic())
