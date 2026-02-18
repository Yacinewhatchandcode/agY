#!/usr/bin/env python3
"""
Comprehensive test script to verify all 5 fixes:
1. /system/status endpoint
2. Pydantic V2 compatibility
3. FastAPI lifespan handlers
4. Semantic orchestrator verification
5. Robust agent error handling
"""

import asyncio
import sys
from datetime import datetime

import httpx


class TestResults:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []

    def add_pass(self, test_name: str, message: str = ""):
        self.passed.append((test_name, message))
        print(f"✅ PASS: {test_name}")
        if message:
            print(f"   {message}")

    def add_fail(self, test_name: str, error: str):
        self.failed.append((test_name, error))
        print(f"❌ FAIL: {test_name}")
        print(f"   Error: {error}")

    def add_warning(self, test_name: str, message: str):
        self.warnings.append((test_name, message))
        print(f"⚠️  WARN: {test_name}")
        print(f"   {message}")

    def print_summary(self):
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"✅ Passed: {len(self.passed)}")
        print(f"❌ Failed: {len(self.failed)}")
        print(f"⚠️  Warnings: {len(self.warnings)}")
        print("=" * 80)

        if self.failed:
            print("\nFailed Tests:")
            for name, error in self.failed:
                print(f"  • {name}: {error}")

        return len(self.failed) == 0


async def test_system_status_endpoint(results: TestResults):
    """Test 1: /system/status endpoint exists and works"""
    print("\n" + "=" * 80)
    print("TEST 1: /system/status Endpoint")
    print("=" * 80)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://localhost:8000/system/status", timeout=5.0
            )

            if response.status_code == 200:
                data = response.json()

                # Validate response structure
                required_fields = ["status", "service", "timestamp", "components"]
                missing = [f for f in required_fields if f not in data]

                if missing:
                    results.add_fail(
                        "System Status Endpoint", f"Missing required fields: {missing}"
                    )
                else:
                    results.add_pass(
                        "System Status Endpoint",
                        f"Status: {data['status']}, Service: {data['service']}",
                    )

                    # Check components
                    components = data.get("components", {})
                    print(f"   Components: {components}")

            elif response.status_code == 503:
                results.add_warning(
                    "System Status Endpoint",
                    "Endpoint exists but service is unhealthy (503)",
                )
            else:
                results.add_fail(
                    "System Status Endpoint",
                    f"Unexpected status code: {response.status_code}",
                )

    except httpx.ConnectError:
        results.add_fail(
            "System Status Endpoint",
            "Server not running on port 8000. Start with: python server.py",
        )
    except Exception as e:
        results.add_fail("System Status Endpoint", str(e))


def test_pydantic_compatibility(results: TestResults):
    """Test 2: Pydantic V2 compatibility"""
    print("\n" + "=" * 80)
    print("TEST 2: Pydantic V2 Compatibility")
    print("=" * 80)

    try:
        import pydantic

        version = pydantic.__version__
        major_version = int(version.split(".")[0])

        if major_version >= 2:
            results.add_pass(
                "Pydantic V2 Compatibility", f"Using Pydantic v{version} (V2+)"
            )
        else:
            results.add_fail(
                "Pydantic V2 Compatibility", f"Using Pydantic v{version}, should be V2+"
            )

    except ImportError:
        results.add_fail("Pydantic V2 Compatibility", "Pydantic not installed")
    except Exception as e:
        results.add_fail("Pydantic V2 Compatibility", str(e))


def test_fastapi_lifespan(results: TestResults):
    """Test 3: FastAPI lifespan handlers (no deprecated on_event)"""
    print("\n" + "=" * 80)
    print("TEST 3: FastAPI Lifespan Handlers")
    print("=" * 80)

    try:
        with open("server.py", "r") as f:
            content = f.read()

        # Check for deprecated @app.on_event
        if "@app.on_event" in content:
            results.add_fail(
                "FastAPI Lifespan Handlers",
                "Found deprecated @app.on_event in server.py",
            )
        else:
            # Check for modern lifespan
            if "@asynccontextmanager" in content and "lifespan" in content:
                results.add_pass(
                    "FastAPI Lifespan Handlers",
                    "Using modern @asynccontextmanager lifespan pattern",
                )
            else:
                results.add_warning(
                    "FastAPI Lifespan Handlers",
                    "No @app.on_event found, but lifespan pattern unclear",
                )

    except FileNotFoundError:
        results.add_fail("FastAPI Lifespan Handlers", "server.py not found")
    except Exception as e:
        results.add_fail("FastAPI Lifespan Handlers", str(e))


def test_semantic_verification(results: TestResults):
    """Test 4: Orchestrator uses semantic verification, not keyword matching"""
    print("\n" + "=" * 80)
    print("TEST 4: Semantic Orchestrator Verification")
    print("=" * 80)

    try:
        with open("agents/orchestrator.py", "r") as f:
            content = f.read()

        # Check for old keyword-based approach
        bad_patterns = [
            'if "GOAL_REACHED" in vision_analysis',
            'if "PASS" in vision_analysis',
            'if "BUG" in vision_analysis',
        ]

        found_bad = [p for p in bad_patterns if p in content]

        if found_bad:
            results.add_fail(
                "Semantic Verification", f"Found keyword-based checks: {found_bad}"
            )
        else:
            # Check for semantic verification
            if "verify_step" in content and "product_agent.verify_step" in content:
                results.add_pass(
                    "Semantic Verification",
                    "Using ProductAgent.verify_step for semantic analysis",
                )
            else:
                results.add_warning(
                    "Semantic Verification",
                    "No keyword matching found, but verify_step usage unclear",
                )

    except FileNotFoundError:
        results.add_fail("Semantic Verification", "agents/orchestrator.py not found")
    except Exception as e:
        results.add_fail("Semantic Verification", str(e))


def test_agent_error_handling(results: TestResults):
    """Test 5: Agents have proper retry logic and error handling"""
    print("\n" + "=" * 80)
    print("TEST 5: Agent Error Handling & Retries")
    print("=" * 80)

    files_to_check = {
        "agents/product_agent.py": [
            "max_retries",
            "retry_delay",
            "for attempt in range",
        ],
        "agents/code_agent.py": ["max_retries", "backup_path", "try:", "except"],
    }

    for filepath, required_patterns in files_to_check.items():
        try:
            with open(filepath, "r") as f:
                content = f.read()

            missing = [p for p in required_patterns if p not in content]

            if missing:
                results.add_fail(
                    f"Error Handling ({filepath})", f"Missing patterns: {missing}"
                )
            else:
                # Check for fallback stubs (bad practice)
                if "# Fallback one-step plan" in content and "return [" in content:
                    # This is OK if it's after retry logic
                    if "for attempt in range" in content:
                        results.add_pass(
                            f"Error Handling ({filepath})",
                            "Has retry logic with fallback after exhaustion",
                        )
                    else:
                        results.add_warning(
                            f"Error Handling ({filepath})",
                            "Has fallback but no retry loop detected",
                        )
                else:
                    results.add_pass(
                        f"Error Handling ({filepath})",
                        "Has retry logic and proper error handling",
                    )

        except FileNotFoundError:
            results.add_fail(f"Error Handling ({filepath})", "File not found")
        except Exception as e:
            results.add_fail(f"Error Handling ({filepath})", str(e))


def test_imports(results: TestResults):
    """Bonus: Test that all required imports work"""
    print("\n" + "=" * 80)
    print("BONUS TEST: Import Validation")
    print("=" * 80)

    modules_to_test = [
        ("langchain", "LangChain"),
        ("langchain_ollama", "LangChain Ollama"),
        ("langchain_core", "LangChain Core"),
        ("pydantic", "Pydantic"),
        ("fastapi", "FastAPI"),
        ("httpx", "HTTPX"),
        ("playwright.async_api", "Playwright"),
    ]

    all_passed = True
    for module_name, display_name in modules_to_test:
        try:
            __import__(module_name)
            print(f"   ✅ {display_name}")
        except ImportError as e:
            print(f"   ❌ {display_name}: {e}")
            all_passed = False

    if all_passed:
        results.add_pass("Import Validation", "All required modules importable")
    else:
        results.add_fail("Import Validation", "Some modules failed to import")


async def main():
    print("=" * 80)
    print("ANTIGRAVITY AGENT - FIX VERIFICATION SUITE")
    print("=" * 80)
    print(f"Start Time: {datetime.now().isoformat()}")
    print()

    results = TestResults()

    # Run all tests
    await test_system_status_endpoint(results)
    test_pydantic_compatibility(results)
    test_fastapi_lifespan(results)
    test_semantic_verification(results)
    test_agent_error_handling(results)
    test_imports(results)

    # Print summary
    success = results.print_summary()

    print(f"\nEnd Time: {datetime.now().isoformat()}")
    print("=" * 80)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
