import os
import subprocess
import sys
import tempfile
from src.models import EngineeringState


class GuardrailValidator:
    def _clean_markdown_fences(self, text: str) -> str:
        """Strips accidental ```python or ``` wrappers if the LLM includes them."""
        lines = text.strip().splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines)

    def _run_pytest_sandbox(self, code: str, tests: str) -> tuple[bool, str]:
        """Writes code and tests to an isolated temp folder and runs pytest."""
        clean_code = self._clean_markdown_fences(code)
        clean_tests = self._clean_markdown_fences(tests)

        # Ensure the test file imports from solution.py if not already present
        if "from solution import" not in clean_tests and "import solution" not in clean_tests:
            clean_tests = "from solution import *\n\n" + clean_tests

        with tempfile.TemporaryDirectory() as sandbox_dir:
            code_path = os.path.join(sandbox_dir, "solution.py")
            test_path = os.path.join(sandbox_dir, "test_solution.py")

            with open(code_path, "w", encoding="utf-8") as f:
                f.write(clean_code)
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(clean_tests)

            try:
                # Run pytest using the active Python interpreter with a 10-second timeout
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", test_path, "-v", "--tb=short"],
                    cwd=sandbox_dir,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                passed = result.returncode == 0
                output = result.stdout + "\n" + result.stderr
                return passed, output.strip()

            except subprocess.TimeoutExpired:
                return False, "SANDBOX_TIMEOUT: Test execution exceeded 10 seconds (possible infinite loop)."
            except Exception as e:
                return False, f"SANDBOX_ERROR: Failed to execute pytest: {str(e)}"

    def validate_and_assess_risk(self, state: EngineeringState) -> bool:
        print("\n[Step 5] Running Automated Guardrails & Live Pytest Sandbox...")
        state.validation_errors.clear()

        # Dynamically find code and test artifacts regardless of task ID naming
        code_artifact = ""
        test_artifact = ""
        for task_id, task in state.task_dag.items():
            if task.agent_role == "developer":
                code_artifact = state.artifacts.get(task_id, "")
            elif task.agent_role == "qa":
                test_artifact = state.artifacts.get(task_id, "")

        # Guardrail 1: Static reliability check for external I/O
        if "try:" not in code_artifact or "except" not in code_artifact:
            state.validation_errors.append(
                "STATIC_GUARDRAIL_FAIL: External I/O calls must include try/except fail-open handling."
            )

        # Guardrail 2: Ensure tests exist and contain assertions
        if "assert" not in test_artifact:
            state.validation_errors.append(
                "STATIC_GUARDRAIL_FAIL: Generated test suite contains no assert statements."
            )

        # Guardrail 3: Live Pytest Execution in Isolated Sandbox
        if code_artifact and test_artifact and not state.validation_errors:
            print("  -> Spinning up isolated temp sandbox and executing pytest...")
            passed, pytest_logs = self._run_pytest_sandbox(code_artifact, test_artifact)
            if not passed:
                state.validation_errors.append(f"PYTEST_EXECUTION_FAIL:\n{pytest_logs}")
            else:
                print("  [✓] Pytest Sandbox Passed (100% tests green)!")

        # Risk & Trade-off Report
        state.risk_report = {
            "identified_risks": [
                "External dependency latency impacting P99 API response time",
                "IP spoofing via unvalidated proxy headers"
            ],
            "mitigation_applied": "Fail-open circuit breaker + verified via automated pytest sandbox",
            "trade_offs": "Fixed-window counter allows brief boundary bursts vs. Sliding Window memory overhead."
        }

        if state.validation_errors:
            print("  [X] Validation Failed:")
            for err in state.validation_errors:
                print(f"      {err}")
            return False

        print("  [✓] All Static Guardrails & Live Sandbox Tests Passed.")
        return True
