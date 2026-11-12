import json
from src.llm_client import LLMClient
from src.models import EngineeringState, ScenarioType, TaskNode


class PlanningAgents:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def understand_requirement(self, state: EngineeringState) -> bool:
        print("\n[Step 1] Analyzing Requirement Intent & Ambiguities...")
        raw_res = json.loads(self.llm.call("intake", state.raw_requirement))
        state.scenario = ScenarioType(raw_res["scenario"])

        if raw_res["is_ambiguous"]:
            state.ambiguities = raw_res["ambiguities"]
            print(f"  [!] Ambiguities detected: {state.ambiguities}")
            return False  # Halts workflow for human clarification

        state.normalized_spec = raw_res["normalized"]
        print(f"  [✓] Scenario: {state.scenario.value.upper()} | Goal: {state.normalized_spec['goal']}")
        return True

    def reason_codebase(self, state: EngineeringState) -> None:
        if state.scenario != ScenarioType.BROWNFIELD or not state.repo_context:
            print("\n[Step 2] Greenfield/Isolated mode: Skipping existing codebase graph traversal.")
            return

        print("\n[Step 2] Mapping Brownfield Codebase Impact...")
        prompt = f"Spec: {state.normalized_spec} | Repo: {state.repo_context}"
        state.impact_analysis = json.loads(self.llm.call("codebase_reasoner", prompt))
        print(f"  [✓] Impacted Files: {state.impact_analysis['impacted_files']}")
        print(f"  [✓] Data Flow: {state.impact_analysis['data_flow']}")

    def decompose_tasks(self, state: EngineeringState) -> None:
        print("\n[Step 3] Decomposing Work into Execution DAG...")
        tasks_data = json.loads(self.llm.call("decomposer", json.dumps(state.normalized_spec)))
        for t in tasks_data:
            state.task_dag[t["id"]] = TaskNode(
                id=t["id"],
                title=t["title"],
                agent_role=t["role"],
                dependencies=t["deps"]
            )
            print(f"  + Task {t['id']} [{t['role']}]: {t['title']} (Deps: {t['deps']})")
