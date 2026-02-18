import asyncio
import json
from typing import Dict, List

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama


class ProductAgent:
    def __init__(self):
        # using a reasoning model for better planning
        self.llm = ChatOllama(model="deepseek-r1:7b", temperature=0)
        self.max_retries = 3
        self.retry_delay = 1.0

    async def create_test_plan(self, user_goal: str) -> List[Dict]:
        """
        Converts a high-level user goal into a structured list of verification steps.
        Returns a list of dicts with retries and proper error handling.
        """
        prompt = f"""
        You are a Product Manager and QA Lead.
        User Goal: "{user_goal}"

        Break this goal down into a minimal, precise set of verification steps that an autonomous browser agent should perform.
        Focus on visual assertions and functional outcomes.

        Return ONLY a JSON array of objects. Format:
        [
            {{
                "id": 1,
                "description": "Navigate to home page",
                "expected_outcome": "Page title matches application context (e.g. contains 'App Name')"
            }},
            {{
                "id": 2,
                "description": "Inspect header layout",
                "expected_outcome": "Logo is on the left, Navigation is on the right"
            }}
        ]

        Do not include any explanation. Just the JSON array.
        IMPORTANT: Infer the application name from the User Goal. Do not assume 'Antigravity' unless specified.
        """

        for attempt in range(self.max_retries):
            try:
                message = HumanMessage(content=prompt)
                response = await self.llm.ainvoke([message])
                content = response.content

                # Clean reasoning tags if present
                if "<think>" in content:
                    content = content.split("</think>")[-1]

                # Extract JSON
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]

                plan = json.loads(content.strip())

                # Validate structure
                if not isinstance(plan, list) or len(plan) == 0:
                    raise ValueError("Plan must be a non-empty list")

                for step in plan:
                    if not all(
                        key in step for key in ["id", "description", "expected_outcome"]
                    ):
                        raise ValueError(f"Invalid step structure: {step}")

                print(f"✅ Product Agent: Created test plan with {len(plan)} steps")
                return plan

            except json.JSONDecodeError as e:
                print(
                    f"⚠️ Product Agent JSON Parse Error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue

            except Exception as e:
                print(
                    f"⚠️ Product Agent Error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue

        # All retries exhausted - return minimal fallback
        print("❌ Product Agent: All retries exhausted, using fallback plan")
        return [
            {
                "id": 1,
                "description": user_goal,
                "expected_outcome": "Goal is satisfied (fallback plan)",
            }
        ]

    async def verify_step(self, current_state: str, step_criteria: str) -> Dict:
        """
        Compares the current visual/DOM state against the acceptance criteria.
        Uses retry logic for robust verification.
        """
        prompt = f"""
        You are a QA Analyst performing semantic verification.

        Acceptance Criteria: "{step_criteria}"
        Current Observation: "{current_state}"

        Analyze whether the current state meets the acceptance criteria.
        Be precise and factual.

        Return JSON: {{ "pass": true/false, "reason": "Detailed explanation of what you observed and why it passes or fails" }}
        """

        for attempt in range(self.max_retries):
            try:
                message = HumanMessage(content=prompt)
                response = await self.llm.ainvoke([message])
                content = response.content

                # Clean reasoning tags if present
                if "<think>" in content:
                    content = content.split("</think>")[-1]

                # Extract JSON
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]

                result = json.loads(content.strip())

                # Validate structure
                if not isinstance(result, dict) or "pass" not in result:
                    raise ValueError("Response must include 'pass' field")

                if "reason" not in result:
                    result["reason"] = "No reason provided"

                print(
                    f"✅ Product Agent: Verification {'passed' if result['pass'] else 'failed'} - {result['reason']}"
                )
                return result

            except json.JSONDecodeError as e:
                print(
                    f"⚠️ Product Agent Verification Parse Error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue

            except Exception as e:
                print(
                    f"⚠️ Product Agent Verification Error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue

        # All retries exhausted
        print("❌ Product Agent: Verification failed after all retries")
        return {
            "pass": False,
            "reason": "Failed to parse verification response after multiple retries. Manual review required.",
        }
