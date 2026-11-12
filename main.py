from dotenv import load_dotenv
load_dotenv()

import json
import os
from src.orchestrator import SDLCOrchestrator


def build_engineering_summary(state) -> dict:
    """Produces the structured engineering summary required by Deliverable 8."""
    return {
        "raw_requirement": state.raw_requirement,
        "scenario_classification": state.scenario.value if state.scenario else "unknown",
        "human_approved": state.human_approved,
        "ambiguities_detected": state.ambiguities,
        "normalized_specification": state.normalized_spec,
        "brownfield_impact_analysis": state.impact_analysis,
        "implementation_plan_and_rationale": {
            "rationale": state.plan_rationale,
            "task_dag": {
                tid: {
                    "title": t.title,
                    "role": t.agent_role,
                    "dependencies": t.dependencies,
                    "status": t.status.value
                }
                for tid, t in state.task_dag.items()
            }
        },
        "generated_artifacts": state.artifacts,
        "risks_tradeoffs_and_validation": {
            "risk_and_tradeoff_report": state.risk_report,
            "validation_strategy": "Static I/O fail-open AST check + isolated subprocess pytest execution",
            "self_healing_iterations_used": state.iteration_count
        },
        "assumptions_and_limitations": state.assumptions_and_limitations
    }


def save_individual_files(state, folder: str = "outputs") -> None:
    os.makedirs(folder, exist_ok=True)
    role_to_filename = {
        "architect": "openapi_contract.yaml",
        "developer": "url_shortener.py",
        "qa": "test_url_shortener.py",
        "tech_writer": "DESIGN_DOC.md"
    }
    for task_id, task in state.task_dag.items():
        filename = role_to_filename.get(task.agent_role)
        content = state.artifacts.get(task_id, "")
        if filename and content:
            lines = content.strip().splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned_text = "\n".join(lines)

            # Align sandbox import 'solution' with saved filename 'url_shortener'
            if filename == "test_url_shortener.py":
                cleaned_text = cleaned_text.replace("from solution import", "from url_shortener import")
                cleaned_text = cleaned_text.replace("import solution", "import url_shortener as solution")

            with open(os.path.join(folder, filename), "w", encoding="utf-8") as f:
                f.write(cleaned_text)


def run_all_deliverable_examples():
    """Generates the 3 required example outputs (Greenfield, Brownfield, Ambiguous) for GitHub."""
    os.makedirs("outputs/examples", exist_ok=True)
    engine = SDLCOrchestrator(max_retries=2, auto_approve=True)

    # 1. Mandatory Use Case (Greenfield)
    print("\n================ 1. MANDATORY USE CASE: URL SHORTENER ================")
    url_req = (
        "Build a scalable URL shortener service with APIs, persistence, and analytics. "
        "Include endpoints to shorten a URL, redirect/resolve a short code, and fetch click analytics "
        "using SQLite persistence and base62 encoding, supporting 1000 read QPS with sub-50ms latency."
    )
    s1 = engine.run(url_req)
    with open("outputs/examples/1_greenfield_url_shortener.json", "w", encoding="utf-8") as f:
        json.dump(build_engineering_summary(s1), f, indent=2)
    save_individual_files(s1, folder="outputs")

    # 2. Brownfield Scenario
    print("\n================ 2. BROWNFIELD SCENARIO ================")
    repo_context = {
        "services": ["url-shortener-service"],
        "files": ["src/api/routes/urls.py", "src/db/storage.py", "src/analytics/tracker.py"],
        "dependencies": ["fastapi", "sqlite3", "pytest"]
    }
    s2 = engine.run(
        "Update the existing URL redirect endpoint in src/api/routes/urls.py to check an optional "
        "expires_at Unix epoch UTC timestamp column in SQLite. Return HTTP 302 redirect for valid links, "
        "treat null expires_at as never expiring, and return HTTP 410 Gone with JSON {'detail': 'Link expired'} for expired links.",
        repo_context=repo_context
    )
    with open("outputs/examples/2_brownfield_expiration.json", "w", encoding="utf-8") as f:
        json.dump(build_engineering_summary(s2), f, indent=2)

    # 3. Ambiguous Scenario
    print("\n================ 3. AMBIGUOUS SCENARIO ================")
    s3 = engine.run("Make the link service handle more traffic and give better stats.")
    with open("outputs/examples/3_ambiguous_requirement.json", "w", encoding="utf-8") as f:
        json.dump(build_engineering_summary(s3), f, indent=2)

    print("\n[✓] All 3 example outputs and runnable URL shortener files saved to outputs/!")


def main():
    print("====================================================")
    print("   AGENTIC SDLC SYSTEM (Controlled Autonomy)        ")
    print("====================================================")
    print("1. Interactive Mode (Mandatory URL Shortener with Human Approval Gates)")
    print("2. Generate All 3 Deliverable Examples (Greenfield, Brownfield, Ambiguous)")
    mode = input("\nSelect mode (1 or 2): ").strip()

    if mode == "2":
        run_all_deliverable_examples()
        return

    engine = SDLCOrchestrator(max_retries=2, auto_approve=False)
    default_req = "Build a scalable URL shortener service with APIs, persistence, and analytics."
    requirement = input("\nEnter requirement (or press Enter for Mandatory Use Case):\n> ").strip() or default_req

    state = engine.run(requirement)

    while state.ambiguities:
        print("\n[?] Ambiguities detected. Please clarify:")
        for idx, q in enumerate(state.ambiguities, 1):
            print(f"    {idx}. {q}")
        clarification = input("\nProvide details:\n> ").strip()
        requirement = f"{requirement} | Clarification: {clarification}"
        state = engine.run(requirement)

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/final_engineering_summary.json", "w", encoding="utf-8") as f:
        json.dump(build_engineering_summary(state), f, indent=2)
    save_individual_files(state, folder="outputs")
    print("\n[✓] Saved structured engineering summary and runnable URL shortener to outputs/!")


if __name__ == "__main__":
    main()
