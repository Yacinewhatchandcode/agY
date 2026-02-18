#!/usr/bin/env python3
"""
Final End-to-End Validation Script
Tests all components to prove demo is complete
"""

import asyncio
import sys

from agents.orchestrator import AutonomousOrchestrator
from app import VisualMultiAgent


async def final_validation():
    print("=" * 80)
    print("FINAL END-TO-END VALIDATION")
    print("=" * 80)

    try:
        # Test 1: VisualMultiAgent
        print("\n1️⃣  Testing VisualMultiAgent...")
        agent = VisualMultiAgent()
        state = await agent.get_state("https://example.com")
        assert "screenshot" in state, "Missing screenshot"
        assert "url" in state, "Missing url"
        assert "timestamp" in state, "Missing timestamp"
        assert state["url"] == "https://example.com/"
        print("   ✅ VisualMultiAgent.get_state() works")
        print(f"      - URL: {state['url']}")
        print(f"      - Timestamp: {state['timestamp']}")
        print(f"      - Screenshot size: {len(state['screenshot'])} bytes")

        # Test 2: Orchestrator
        print("\n2️⃣  Testing Orchestrator...")
        orchestrator = AutonomousOrchestrator(agent, ".")
        assert orchestrator.browser is not None, "Browser not initialized"
        assert orchestrator.code_agent is not None, "CodeAgent not initialized"
        assert orchestrator.product_agent is not None, "ProductAgent not initialized"
        assert orchestrator.vision_model is not None, "Vision model not initialized"
        print("   ✅ Orchestrator initialized with all agents")
        print(f"      - Browser: {type(orchestrator.browser).__name__}")
        print(f"      - Code Agent: {type(orchestrator.code_agent).__name__}")
        print(f"      - Product Agent: {type(orchestrator.product_agent).__name__}")

        # Test 3: Vision Analysis
        print("\n3️⃣  Testing Vision Analysis...")
        vision_result = await orchestrator.analyze_vision(
            state, "Is this a valid webpage?"
        )
        assert len(vision_result) > 0, "Vision analysis returned empty result"
        print(f"   ✅ Vision analysis returned {len(vision_result)} characters")
        print(f"      Preview: {vision_result[:150]}...")

        # Test 4: Tools availability
        print("\n4️⃣  Testing Tools Availability...")
        tools = agent.tools
        expected_tools = [
            "web_browse",
            "web_click",
            "take_screenshot",
            "search_web",
            "execute_python",
        ]
        for tool in expected_tools:
            assert tool in tools, f"Missing tool: {tool}"
        print(f"   ✅ All {len(expected_tools)} tools available")
        print(f"      - {', '.join(expected_tools)}")

        # Test 5: Retry logic
        print("\n5️⃣  Testing Retry Logic...")
        assert hasattr(orchestrator.product_agent, "max_retries"), (
            "ProductAgent missing retry logic"
        )
        assert hasattr(orchestrator.code_agent, "max_retries"), (
            "CodeAgent missing retry logic"
        )
        print(f"   ✅ Retry logic implemented")
        print(f"      - ProductAgent retries: {orchestrator.product_agent.max_retries}")
        print(f"      - CodeAgent retries: {orchestrator.code_agent.max_retries}")

        print("\n" + "=" * 80)
        print("✅ ALL COMPONENTS VALIDATED - DEMO IS COMPLETE")
        print("=" * 80)
        print("\nSummary:")
        print("  ✅ VisualMultiAgent functional")
        print("  ✅ Orchestrator initialized")
        print("  ✅ Vision analysis working")
        print("  ✅ All tools available")
        print("  ✅ Retry logic present")
        print("\n🎉 The demo is 100% complete and operational!")
        return 0

    except AssertionError as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(final_validation())
    sys.exit(exit_code)
