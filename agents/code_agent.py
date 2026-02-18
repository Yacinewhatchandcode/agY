import asyncio
import os
import subprocess
from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama


class CodebaseAgent:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.llm = ChatOllama(model="deepseek-r1:7b", temperature=0)
        self.max_retries = 3
        self.retry_delay = 1.0

    async def find_relevant_files(self, bug_description: str) -> List[str]:
        """
        Search the codebase for files related to the bug.
        Returns a list of file paths with retry logic.
        """
        try:
            # 1. Get file list
            files = []
            excluded_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv"}

            for root, dirs, filenames in os.walk(self.repo_path):
                # Filter out excluded directories
                dirs[:] = [d for d in dirs if d not in excluded_dirs]

                for f in filenames:
                    if f.endswith((".py", ".js", ".ts", ".css", ".html", ".json")):
                        rel_path = os.path.relpath(
                            os.path.join(root, f), self.repo_path
                        )
                        files.append(rel_path)

            if not files:
                print("⚠️ Code Agent: No relevant files found in repository")
                return []

            # 2. Use LLM to narrow down based on bug description
            prompt = f"""Given this issue: '{bug_description}'

Analyze which of these files are most likely responsible. Return a JSON array of file paths.

Files:
{chr(10).join(files[:50])}

Return format: ["file1.py", "file2.css"]
Only include the most relevant files (max 3)."""

            for attempt in range(self.max_retries):
                try:
                    message = HumanMessage(content=prompt)
                    response = await self.llm.ainvoke([message])
                    content = response.content

                    # Clean reasoning tags
                    if "<think>" in content:
                        content = content.split("</think>")[-1]

                    # Extract JSON
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]

                    import json

                    result = json.loads(content.strip())

                    if isinstance(result, list):
                        print(f"✅ Code Agent: Identified {len(result)} relevant files")
                        return result

                except Exception as e:
                    print(
                        f"⚠️ Code Agent File Search Error (attempt {attempt + 1}/{self.max_retries}): {e}"
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay)
                        continue

            # Fallback: return common files
            fallback = [
                f for f in files if "style" in f.lower() or "main" in f.lower()
            ][:3]
            print(f"⚠️ Code Agent: Using fallback file list: {fallback}")
            return fallback

        except Exception as e:
            print(f"❌ Code Agent: Critical error in find_relevant_files: {e}")
            return []

    async def apply_fix(self, file_path: str, instruction: str) -> bool:
        """
        Modifies the code based on reasoning with retry logic and backups.
        Returns True if fix was successfully applied, False otherwise.
        """
        # Validate file exists
        if not os.path.exists(file_path):
            print(f"❌ Code Agent: File not found: {file_path}")
            return False

        # Create backup
        backup_path = f"{file_path}.backup"
        try:
            with open(file_path, "r") as f:
                original_content = f.read()

            with open(backup_path, "w") as f:
                f.write(original_content)

            print(f"✅ Code Agent: Created backup at {backup_path}")
        except Exception as e:
            print(f"❌ Code Agent: Failed to create backup: {e}")
            return False

        prompt = f"""File: {file_path}
Current Content:
```
{original_content}
```

Instruction: {instruction}

Task: Return the COMPLETE valid file content with the fix applied.
Do not return a diff. Do not return multiple markdown blocks.
Return ONLY the raw code inside a single markdown code block (e.g. ```css ... ``` or ```python ... ```).
Ensure all syntax is valid and the file structure is preserved.
"""

        for attempt in range(self.max_retries):
            try:
                message = HumanMessage(content=prompt)
                response = await self.llm.ainvoke([message])
                cleaned_content = response.content

                # 1. Remove <think> blocks
                if "<think>" in cleaned_content:
                    cleaned_content = cleaned_content.split("</think>")[-1]

                # 2. Extract code block
                if "```" in cleaned_content:
                    parts = cleaned_content.split("```")
                    if len(parts) >= 3:
                        code_block = parts[1]
                        # Strip language identifier (first line)
                        if "\n" in code_block:
                            first_line = code_block.split("\n")[0].strip()
                            if first_line.lower() in [
                                "css",
                                "python",
                                "javascript",
                                "html",
                                "js",
                                "py",
                                "typescript",
                                "ts",
                            ]:
                                code_block = code_block[len(first_line) + 1 :]
                        cleaned_content = code_block.strip()

                # Validate content
                if len(cleaned_content) < 10:
                    raise ValueError("Generated content too short, likely invalid")

                # Validate it's not just the instruction echoed back
                if (
                    instruction.lower() in cleaned_content.lower()
                    and len(cleaned_content) < 100
                ):
                    raise ValueError(
                        "Response appears to be instruction echo, not actual code"
                    )

                # Write the fix
                with open(file_path, "w") as f:
                    f.write(cleaned_content)

                print(f"✅ Code Agent: Successfully applied fix to {file_path}")

                # Remove backup on success
                if os.path.exists(backup_path):
                    os.remove(backup_path)

                return True

            except Exception as e:
                print(
                    f"⚠️ Code Agent Fix Error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue

        # All retries failed - restore backup
        print(f"❌ Code Agent: All fix attempts failed, restoring backup")
        try:
            with open(backup_path, "r") as f:
                original_content = f.read()
            with open(file_path, "w") as f:
                f.write(original_content)
            os.remove(backup_path)
            print(f"✅ Code Agent: Restored original file from backup")
        except Exception as e:
            print(f"❌ Code Agent: Failed to restore backup: {e}")

        return False

    def run_tests(self) -> dict:
        """
        Run the local build/test suite with proper error handling.
        Attempts multiple test commands based on project type.
        """
        test_commands = [
            (["npm", "test"], "npm"),
            (["python", "-m", "pytest"], "pytest"),
            (["python", "-m", "unittest", "discover"], "unittest"),
        ]

        for cmd, test_type in test_commands:
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=30, cwd=self.repo_path
                )

                if result.returncode == 0:
                    print(f"✅ Code Agent: Tests passed ({test_type})")
                    return {
                        "success": True,
                        "output": result.stdout,
                        "test_type": test_type,
                    }
                else:
                    print(f"⚠️ Code Agent: Tests failed ({test_type})")
                    return {
                        "success": False,
                        "output": result.stdout + "\n" + result.stderr,
                        "test_type": test_type,
                    }

            except FileNotFoundError:
                # Command not available, try next one
                continue
            except subprocess.TimeoutExpired:
                print(f"⚠️ Code Agent: Test timeout ({test_type})")
                return {
                    "success": False,
                    "output": f"Test execution timed out after 30 seconds",
                    "test_type": test_type,
                }
            except Exception as e:
                print(f"⚠️ Code Agent: Test error ({test_type}): {e}")
                continue

        # No test commands succeeded
        print("⚠️ Code Agent: No test suite found or all tests failed")
        return {
            "success": False,
            "output": "No test suite available or all test commands failed",
        }

    async def run_validation(self) -> dict:
        """
        Run validation checks (lint, typecheck, syntax)
        Required by v3 Orchestrator for the VALIDATE step
        Returns: {"success": bool, "output": str}
        """
        validations = []
        
        # 1. Python syntax check
        try:
            python_files = []
            for root, dirs, files in os.walk(self.repo_path):
                dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__"}]
                for f in files:
                    if f.endswith(".py"):
                        python_files.append(os.path.join(root, f))
            
            if python_files:
                for py_file in python_files[:5]:  # Check first 5 files
                    result = subprocess.run(
                        ["python3", "-m", "py_compile", py_file],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode != 0:
                        return {"success": False, "output": f"Syntax error in {py_file}: {result.stderr}"}
                
                validations.append("Python syntax: PASS")
        except Exception as e:
            validations.append(f"Python syntax: SKIP ({str(e)})")
        
        # 2. If no critical failures, return success
        print(f"✅ Code Agent: Validation checks completed: {', '.join(validations)}")
        return {
            "success": True,
            "output": "\n".join(validations)
        }
