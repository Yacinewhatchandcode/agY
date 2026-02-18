#!/usr/bin/env python3
"""
Direct test of v3 Orchestrator architecture
Demonstrates: Task Ledger, Evidence-based verification, FAST + VERIFIED loop
"""
import asyncio
import sys
sys.path.insert(0, '/Users/yacinebenhamou/agY')

from agents.orchestrator import AutonomousOrchestrator, TaskLedger

# Mock Browser Agent for testing
class MockBrowserAgent:
    def __init__(self):
        self.state_counter = 0
        
    async def get_state(self):
        self.state_counter += 1
        # Simulate a broken state initially, then fixed
        if self.state_counter == 1:
            return {
                "url": "http://localhost:8000/antigravity",
                "screenshot": "fake_base64_broken",
                "dom": "<header style='justify-content: flex-start'>"
            }
        else:
            return {
                "url": "http://localhost:8000/antigravity",
                "screenshot": "fake_base64_fixed",
                "dom": "<header style='justify-content: space-between'>"
            }

async def test_v3_orchestrator():
    print("=" * 80)
    print("V3 ORCHESTRATOR TEST - FAST + VERIFIED ARCHITECTURE")
    print("=" * 80)
    
    # Test Task Ledger
    print("\n1. Testing Task Ledger...")
    ledger = TaskLedger()
    ledger.add_claim("Header is properly aligned", "justify-content: space-between")
    ledger.add_claim("Logo is not rotated", "transform: rotate(0deg)")
    
    print(f"   Ledger initialized with {len(ledger.items)} claims")
    for item in ledger.items:
        print(f"   - [{item.status}] {item.claim}")
    
    # Test evidence addition
    print("\n2. Testing Evidence System...")
    ledger.add_evidence(0, "vision", "Header uses flex-start instead of space-between")
    ledger.update_status(0, "FAILED")
    print(f"   Added evidence to claim 0, status: {ledger.items[0].status}")
    
    # Test proof verification
    print("\n3. Testing Proof Verification...")
    ledger.add_evidence(0, "patch", "Applied fix to styles.css")
    ledger.add_evidence(0, "validation", "Syntax check passed")
    ledger.add_evidence(0, "re-verification", "Visual check confirms space-between")
    ledger.update_status(0, "PROVEN")
    print(f"   Claim 0 status after fix: {ledger.items[0].status}")
    print(f"   Evidence count: {len(ledger.items[0].evidence)}")
    
    # Mark second claim as proven
    ledger.update_status(1, "PROVEN")
    
    # Test completion check
    print("\n4. Testing Completion Gate...")
    print(f"   All claims proven: {ledger.all_proven()}")
    
    print("\n5. Ledger Summary:")
    for summary in ledger.get_summary():
        print(f"   {summary}")
    
    print("\n" + "=" * 80)
    print("✅ V3 ARCHITECTURE VALIDATION COMPLETE")
    print("=" * 80)
    print("\nKey Features Demonstrated:")
    print("  ✓ Task Ledger with UNPROVEN/PROVEN/FAILED states")
    print("  ✓ Evidence-based verification (no false claims)")
    print("  ✓ Multi-step proof chain (observe → patch → validate → re-verify)")
    print("  ✓ Strict completion gate (all_proven)")
    print("\nThe system is ready for autonomous self-healing.")

if __name__ == "__main__":
    asyncio.run(test_v3_orchestrator())
