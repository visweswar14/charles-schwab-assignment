from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Optional

from src.agents import PlanningAgents
from src.guardrails import GuardrailValidator
from src.llm_client import LLMClient
from src.models import EngineeringState, TaskNode, TaskStatus


class SDLCOrchestrator:
    def __init__(self, max_retries: int = 2, auto_approve: bool = False):
        self.max_retries = max_retries
        self.auto_approve = auto_approve
        self.llm = LLMClient()
        self.planner = PlanningAgents(self.llm)
        self.validator = GuardrailValidator()

    def _human_gate(self, prompt_message: str) -> bool:
        """Controlled Autonomy Checkpoint: Requires explicit human sign-off."""
        if self.auto_approve:
            print(f"\n[Controlled Autonomy - Auto-Approved]: {prompt_message}")
            return True
        choice = input(f"\n[Human Oversight Gate] {prompt_message} (y/n): ").strip().lower()
        return choice in ["y", "yes", ""]

    def _execute_dag(self, state: EngineeringState, feedback_context: str = "") -> None:
        print(f"\n[Step 4] Orchestrating Multi-Agent DAG Execution (Pass {state.iteration_count + 1})...")

        def execute_node(task: TaskNode) -> TaskNode:
            task.status = TaskStatus.RUNNING
            dev_code = next(
                (state.artifacts[tid] for tid, t in state.task_dag.items()
                 if t.agent_role == "developer" and tid in state.artifacts),
                ""
            )
            extra = f" | Existing Developer Code to Test:\n{dev_code}" if task.agent_role == "qa" and dev_code else ""
            context = f"Spec: {state.normalized_spec} | Impact: {state.impact_analysis}{extra} | {feedback_context}"
            task.output = self.llm.call(task.agent_role, context)
            task.status = TaskStatus.COMPLETED
            return task

        while any(t.status != TaskStatus.COMPLETED for t in state.task_dag.values()):
            ready_tasks = [
                t for t in state.task_dag.values()
                if t.status == TaskStatus.PENDING and all(
                    state.task_dag[dep].status == TaskStatus.COMPLETED for dep in t.dependencies
                )
            ]

            if not ready_tasks:
                raise RuntimeError("Deadlock detected in task DAG.")

            print(f"  -> Executing batch in parallel: {[t.id for t in ready_tasks]}")
            with ThreadPoolExecutor(max_workers=len(ready_tasks)) as executor:
                futures = [executor.submit(execute_node, t) for t in ready_tasks]
                for future in as_completed(futures):
                    completed_task = future.result()
                    state.artifacts[completed_task.id] = completed_task.output

    def run(self, requirement: str, repo_context: Optional[Dict[str, Any]] = None) -> EngineeringState:
        state = EngineeringState(raw_requirement=requirement, repo_context=repo_context)

        # Phase 1: Requirement Triage
        if not self.planner.understand_requirement(state):
            return state

        # Phase 2 & 3: Architecture & Planning
        self.planner.reason_codebase(state)
        self.planner.decompose_tasks(state)
        state.plan_rationale = (
            f"Decomposed '{state.normalized_spec.get('goal')}' into {len(state.task_dag)} "
            f"contract-first tasks. API schema executes first to unblock implementation and test verification."
        )

        # Controlled Autonomy Gate 1: Human approves the task plan before code generation
        if not self._human_gate("Approve this Task Execution Plan before agents generate code?"):
            print("[!] Execution halted by human reviewer at Planning Gate.")
            return state

        # Phase 4 & 5: Autonomous Execution + Self-Healing Validation Loop
        feedback = ""
        while state.iteration_count <= self.max_retries:
            self._execute_dag(state, feedback_context=feedback)
            if self.validator.validate_and_assess_risk(state):
                break

            state.iteration_count += 1
            if state.iteration_count > self.max_retries:
                print("\n[!] Max retries exceeded. Escalating to human reviewer with partial artifacts.")
                break

            print("\n[Recovery] Routing errors back to Developer, QA & Tech Writer agents...")
            for tid, task in state.task_dag.items():
                if task.agent_role in ["developer", "qa", "tech_writer"]:
                    task.status = TaskStatus.PENDING
            feedback = f"FIX_REQUIRED: {'; '.join(state.validation_errors)}"

        # Populate Assumptions & Limitations for Final Report
        state.assumptions_and_limitations = [
            "Assumes stateless horizontal scaling behind a load balancer.",
            "SQLite persistence used for standalone prototype demoability; swap for Redis + PostgreSQL in production.",
            "Analytics events are recorded synchronously in prototype; async message queue recommended for high throughput."
        ]

        # Controlled Autonomy Gate 2: Final Human Sign-Off
        state.human_approved = self._human_gate("All guardrails passed. Approve final PR package for release?")
        return state
