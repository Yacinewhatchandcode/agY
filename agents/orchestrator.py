import asyncio
import json
import base64
from typing import List, Dict, Any, Literal
from datetime import datetime
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from config import MODEL_LLM_VISION
from agents.code_agent import CodebaseAgent
from agents.product_agent import ProductAgent

# --- v3 DATA STRUCTURES ---

class TaskLedgerItem:
    def __init__(self, claim: str, criteria: str):
        self.claim = claim
        self.criteria = criteria
        self.evidence = [] # List of {type, data, timestamp}
        self.status: Literal["UNPROVEN", "PROVEN", "FAILED"] = "UNPROVEN"
        self.next_action = "OBSERVE"

class TaskLedger:
    def __init__(self):
        self.items: List[TaskLedgerItem] = []
        
    def add_claim(self, claim: str, criteria: str):
        self.items.append(TaskLedgerItem(claim, criteria))
        
    def add_evidence(self, index: int, evidence_type: str, data: str):
        if 0 <= index < len(self.items):
            self.items[index].evidence.append({
                "type": evidence_type, 
                "data": data, 
                "timestamp": datetime.now().isoformat()
            })
            
    def update_status(self, index: int, status: str):
        if 0 <= index < len(self.items):
            self.items[index].status = status

    def get_summary(self):
        return [
            f"[{item.status}] {item.claim} (Criteria: {item.criteria})" 
            for item in self.items
        ]
        
    def all_proven(self):
        return all(item.status == "PROVEN" for item in self.items)

# --- v3 ORCHESTRATOR ---

class AutonomousOrchestrator:
    """
    AUTHORITY: I am the only entity allowed to decide plan, mutate code, and mark tasks DONE.
    MODEL: v3 FAST + VERIFIED
    """
    def __init__(self, browser_agent, repo_path: str = "."):
        self.browser = browser_agent
        # C) CODEBASE ENGINEER AGENT (Consolidated Engineer)
        self.engineer = CodebaseAgent(repo_path)
        # Helper for Intent Derivation (Product logic is internal to Orchestrator's "Intent" phase)
        self.product_helper = ProductAgent() 
        # B) SEMANTICS (Vision Capability)
        self.vision_model = ChatOllama(model=MODEL_LLM_VISION, temperature=0)
        
        self.ledger = TaskLedger()
        self.reasoning_steps = []
        self.is_running = False

    async def emit_step(self, text: str, status: str = "active"):
        """Emit telemetry to UI"""
        step = {"text": text, "status": status, "timestamp": datetime.now().isoformat()}
        self.reasoning_steps.append(step)
        print(f"🧠 [{status.upper()}] {text}")

    async def run_task(self, user_command: str):
        self.is_running = True
        self.ledger = TaskLedger() # Reset Ledger
        self.reasoning_steps = []
        
        await self.emit_step(f"COMMAND: {user_command}", "start")

        # 1. INTENT & ACCEPTANCE CRITERIA
        await self.emit_step("Deriving Pass/Fail Criteria...")
        plan = await self.product_helper.create_test_plan(user_command)
        
        for step in plan:
            self.ledger.add_claim(step['description'], step['expected_outcome'])
            
        await self.emit_step(f"Ledger Initialized with {len(self.ledger.items)} Claims.", "info")

        # EXECUTION LOOP
        all_proven = False
        iteration = 0
        max_loop_limit = 10 # Safety break
        
        while not all_proven and self.is_running and iteration < max_loop_limit:
            iteration += 1
            await self.emit_step(f"--- LOOP START (Iteration {iteration}) ---", "info")
            
            # Iterate through UNPROVEN claims
            for idx, item in enumerate(self.ledger.items):
                if item.status == "PROVEN": continue
                if not self.is_running: break

                await self.emit_step(f"Processing Claim: {item.claim}")
                
                # 2. OBSERVE (Browser+Semantics)
                await self.emit_step("Role: Browser+Semantics | Action: Observe & Verify")
                state = await self.browser.get_state()
                
                # Semantic Check
                verification_prompt = f"""
                Criteria: {item.criteria}
                Current URL: {state['url']}
                
                Does the attached screenshot/state Prove this criteria is met?
                Return "PROVEN" or "FAILED".
                If FAILED, describe the specific visual/functional discrepancy.
                """
                analysis = await self.analyze_vision(state, verification_prompt)
                
                if "PROVEN" in analysis:
                    self.ledger.update_status(idx, "PROVEN")
                    self.ledger.add_evidence(idx, "vision", analysis)
                    await self.emit_step(f"Claim Proven: {item.criteria}", "success")
                    continue # Move to next claim
                
                # FAILED -> DIAGNOSE & PATCH LOOP
                self.ledger.update_status(idx, "FAILED")
                self.ledger.add_evidence(idx, "failure_trace", analysis)
                await self.emit_step(f"Claim Failed: {analysis}", "warning")
                
                # 3. DIAGNOSE (Engineer)
                await self.emit_step("Role: Engineer | Action: Diagnose Root Cause")
                # Engineer scans codebase
                relevant_files = await self.engineer.find_relevant_files(analysis)
                
                # 4. PATCH (Engineer)
                if relevant_files:
                    target_file = relevant_files[0] if isinstance(relevant_files, list) else relevant_files
                    # In a real scenario, we'd pick the best file. For now, we trust the agent.
                    await self.emit_step(f"Role: Engineer | Action: Patching {target_file}")
                    
                    # Construct smart fix prompt
                    fix_instruction = f"Fix the issue preventing this criteria: '{item.criteria}'. Issue trace: {analysis}"
                    fix_applied = await self.engineer.apply_fix(target_file, fix_instruction)
                    
                    if fix_applied:
                        await self.emit_step("Patch Applied.", "success")
                        
                        # 5. VALIDATE (Engineer)
                        await self.emit_step("Role: Engineer | Action: Validation (Lint/Test)")
                        validation = await self.engineer.run_validation() # Assuming we added this
                        if not validation['success']:
                            await self.emit_step(f"Validation Failed: {validation['output']}", "error")
                            # In v3, we should rollback or fix-forward. For demo, we pause.
                            await self.emit_step("Critical Validation Failure. Pausing.", "error")
                            break
                        else:
                            await self.emit_step("Validation Passed.", "success")
                
                # 6. RE-RUN UI (Browser)
                await self.emit_step("Role: Browser | Action: Re-Run UI Flow (Reload)")
                # Simulating reload/navigation
                # await self.browser.reload() - In our simulated browser env, we'll wait for next loop to capture new state
                await asyncio.sleep(2) 
                
                # We do NOT mark PROVEN here. We loop back to "OBSERVE" in the next iteration 
                # to prove the fix worked.
                await self.emit_step("State reset for verification.", "info")
                
            all_proven = self.ledger.all_proven()
            if not all_proven:
                await asyncio.sleep(1) # Breath
                
        # 7. DONE GATE
        if all_proven:
            await self.emit_step("✅ ALL CLAIMS PROVEN. MISSION COMPLETE.", "completed")
            return "SUCCESS"
        else:
            await self.emit_step("❌ Mission Incomplete after Max Iterations.", "error")
            return "FAILED"

    async def analyze_vision(self, state: dict, prompt: str) -> str:
        """Browser+Semantics Ability"""
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{state['screenshot']}"},
                },
            ]
        )
        response = await self.vision_model.ainvoke([message])
        return response.content
