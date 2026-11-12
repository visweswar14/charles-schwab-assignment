# Agentic SDLC System — Controlled Autonomy Prototype

An end-to-end, multi-agent Software Development Life Cycle (SDLC) orchestration system that transforms raw software requirements into verified, reviewable engineering deliverables under **controlled autonomy**.

---

## 1. Problem Approach & Engineering Philosophy

Traditional LLM coding assistants act as single-turn chatbots—often guessing missing requirements, generating inconsistent interfaces across files, and producing untested code. To solve this as a production-grade engineering workflow, I designed a **state-driven, cyclic multi-agent system** governed by four core principles:

1. **Ambiguity-First Triage:** Before writing any code, an Intake Agent evaluates intent and completeness. If critical engineering constraints (SLAs, persistence engines, HTTP semantics, or metrics) are missing, execution halts safely and requests human clarification.
2. **Contract-First Dependency Orchestration:** Work is decomposed into a **Directed Acyclic Graph (DAG)**. Interface contracts (`OpenAPI 3.0`) are generated first, followed by implementation (`Developer`) and automated test generation (`QA`)—which inspects the exact generated module symbols—and finally documentation (`Tech Writer`).
3. **Closed-Loop Verification & Self-Healing:** Generated artifacts are never trusted blindly. A Guardrail Validator runs static reliability checks (`try/except` verification on external I/O) and executes `pytest` inside an isolated ephemeral sandbox. Failures automatically feed exact stack traces back to the responsible agents for bounded self-correction.
4. **Controlled Autonomy:** Agents execute multi-step technical workflows independently, while humans retain governance at critical checkpoints (clarifying ambiguities, approving the task execution plan, and signing off on the final release package).

---

## 2. System Architecture & Control Flow

```text
[Raw Requirement + Optional Repo Context]
                   │
                   ▼
      ┌─────────────────────────┐
      │ 1. Intake & Triage      │ ──► Ambiguous? ──► [Human Clarification Loop]
      └────────────┬────────────┘
                   │ Normalized Spec
                   ▼
      ┌─────────────────────────┐
      │ 2. Codebase Reasoner    │ (Skipped for Greenfield; maps impacted files/flows for Brownfield)
      └────────────┬────────────┘
                   │
                   ▼
      ┌─────────────────────────┐
      │ 3. Task Decomposer      │ ──► Builds Execution DAG + Plan Rationale
      └────────────┬────────────┘
                   │
                   ▼
      [Human Oversight Gate 1: Approve Execution Plan]
                   │ Approved
                   ▼
      ┌─────────────────────────┐      ┌─────────────────────────────────────┐
      │ 4. Parallel DAG Runner  │ ◄──► │ 5. Specialist Agents (Gemini API)   │
      │ (ThreadPoolExecutor)    │      │ • Architect (OpenAPI 3.0 Schema)    │
      └────────────┬────────────┘      │ • Developer (Python Service Class)  │
                   │                   │ • QA (Standalone Pytest Suite)      │
                   │                   │ • Tech Writer (Markdown Design Doc) │
                   ▼                   └─────────────────────────────────────┘
      ┌─────────────────────────┐
      │ 6. Guardrail & Sandbox  │ ──► Fails Check/Pytest? ──► [Self-Healing Retry (Max 2)]
      └────────────┬────────────┘
                   │ 100% Passed
                   ▼
      [Human Oversight Gate 2: Final Release Sign-Off]
                   │
                   ▼
      [Structured Engineering Summary + Runnable Artifacts]
```

### Repository Structure

```text
agentic-sdlc-prototype/
├── main.py                          # CLI entry point (Interactive & Batch Deliverable modes)
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment variable template for reviewers
├── .gitignore                       # Excludes .env, __pycache__, and .pytest_cache
├── README.md                        # System documentation & evaluation guide
│
├── src/
│   ├── __init__.py
│   ├── models.py                    # Central EngineeringState, TaskNode, and ScenarioType models
│   ├── llm_client.py                # Resilient Gemini client (Pydantic JSON schemas, 429/503 failover)
│   ├── offline_fallback.py          # Deterministic offline simulator for zero-key evaluation
│   ├── agents.py                    # Planning agents (Intake, Brownfield Reasoner, DAG Decomposer)
│   ├── orchestrator.py              # Parallel DAG scheduler, human gates, and self-healing loop
│   └── guardrails.py                # Static I/O reliability checks & isolated subprocess pytest sandbox
│
└── outputs/                         # Generated deliverables & verified scenario reports
    ├── url_shortener.py             # Runnable URL shortener service (Mandatory Use Case)
    ├── test_url_shortener.py        # Automated pytest unit & latency test suite
    ├── pytest_report.txt            # Saved local pytest verification log
    ├── openapi_contract.yaml        # OpenAPI 3.0 API specification
    ├── DESIGN_DOC.md                # Architecture, usage & failure mode documentation
    ├── final_engineering_summary.json # Complete Mode 1 interactive run report
    └── examples/                    # Saved structured engineering summaries for all 3 scenarios
        ├── 1_greenfield_url_shortener.json
        ├── 2_brownfield_expiration.json
        └── 3_ambiguous_requirement.json
```

---

## 3. Setup & Running Instructions

### Prerequisites
* **Python 3.9+**
* Optional: A Google Gemini API key from [Google AI Studio](https://google.com) *(Note: If no API key is configured, the system automatically falls back to an offline simulator so all workflows can still be evaluated out-of-the-box).*

### 1. Clone & Install Dependencies
```bash
git clone <your-github-repository-url>
cd agentic-sdlc-prototype
pip install -r requirements.txt
```

### 2. Configure Environment (Optional for Live LLM Mode)
Copy `.env.example` to `.env` and insert your Gemini API key:
```bash
cp .env.example .env
# Edit .env and set: GEMINI_API_KEY=your_actual_api_key
```

### 3. Run the Agentic SDLC System
```bash
python main.py
```

Choose between two execution modes:
* **Mode `1` (Interactive Controlled Autonomy):** Runs the mandatory URL shortener requirement (`"Build a scalable URL shortener service with APIs, persistence, and analytics."`), prompts for human clarification when ambiguities are detected, and pauses at explicit human approval gates before code generation and final release. Saves results to `outputs/final_engineering_summary.json` and individual artifacts in `outputs/`.
* **Mode `2` (Batch Deliverable Generator):** Automatically executes and saves structured engineering summaries for **Greenfield**, **Brownfield**, and **Ambiguous** scenarios into `outputs/examples/`.

### 4. Verify the Generated URL Shortener
Run the generated `pytest` suite against the produced URL shortener module:
```bash
python -m pytest outputs/test_url_shortener.py -v
```

*Note: Depending on prompt specificity, the QA agent dynamically generates 6–8 unit, edge-case, and latency tests—all verified 100% green in the isolated sandbox (see `outputs/pytest_report.txt` for the saved local test execution log).*

---

## 4. Demonstration of Core Capabilities (Example Scenarios)

The `outputs/` and `outputs/examples/` directories contain complete structured JSON engineering summaries (`implementation_plan_and_rationale`, `generated_artifacts`, `risks_tradeoffs_and_validation`, `assumptions_and_limitations`) from live executions:

1. **Interactive Controlled Autonomy (`outputs/final_engineering_summary.json`):**
   * **Input:** `"Build a scalable URL shortener service with APIs, persistence, and analytics."`
   * **Workflow:** Detected 4 architectural ambiguities (DAU/throughput, slug rules, analytics metrics, persistence), incorporated human clarifications, obtained explicit approval at Gate 1 and Gate 2, and passed 100% of `pytest` unit and sub-50ms latency checks on Pass 1.
2. **Greenfield with Self-Healing (`outputs/examples/1_greenfield_url_shortener.json`):**
   * **Input:** Scalable URL shortener service with APIs, SQLite persistence, base62 encoding, and click analytics.
   * **Self-Healing Highlight:** In Pass 1, `pytest` caught a schema/assertion mismatch (`5 failed, 3 passed`). The orchestrator automatically routed the failure traceback back to the `Developer` and `QA` agents, achieving **100% passing tests (8/8 green)** in Pass 2.
3. **Brownfield (`outputs/examples/2_brownfield_expiration.json`):**
   * **Input:** Update an existing URL redirect endpoint (`src/api/routes/urls.py`) to enforce an optional `expires_at` Unix epoch UTC timestamp column (HTTP `302` for valid/null expiry, HTTP `410 Gone` for expired links).
   * **Codebase Reasoning:** Isolated impacted files (`src/api/routes/urls.py`, `src/db/storage.py`), traced end-to-end request flow, and verified all expiration boundary conditions via `pytest`.
4. **Ambiguous (`outputs/examples/3_ambiguous_requirement.json`):**
   * **Input:** *"Make the link service handle more traffic and give better stats."*
   * **Controlled Triage:** Halted execution prior to planning and surfaced targeted clarifying questions regarding throughput targets (QPS), latency SLAs, and specific observability metrics.

---

## 5. Key Design Decisions, Trade-offs & Assumptions

| Decision | Rationale | Trade-off |
| :--- | :--- | :--- |
| DAG Orchestration with Symbol Sharing | Models tasks as a dependency graph (Architect -> Developer -> QA -> Tech Writer) and passes generated Developer source code into the QA context. | Eliminates import/signature hallucinations between agents while preserving parallel execution capability for independent branches. |
| Pydantic Structured Outputs | Enforces strict JSON schemas (IntakeResponseSchema, ImpactAnalysisSchema, TaskItemSchema) for all planning nodes. | Prevents JSONDecodeError crashes during orchestration without relying on fragile string parsing. |
| Ephemeral Subprocess Pytest Sandbox | Writes solution.py and test_solution.py into tempfile.TemporaryDirectory() and executes sys.executable -m pytest -v with a 10s timeout. | Zero external infrastructure required (works cross-platform without Docker daemon overhead), though less isolated at the OS kernel level than containers. |
| Bounded Self-Healing (Max 2 Retries) | Automatically feeds pytest tracebacks and static guardrail violations back to failing agents, resetting only downstream affected tasks. | Caps API spend and prevents infinite retry loops while reliably fixing syntax, SQLite connection, or assertion bugs. |
| Resilient Multi-Model & Offline Fallback | Includes automatic failover across Gemini models (3.5-flash-lite -> 3.1-flash-lite-preview -> 3.8-flash), RPM pacing, and a deterministic offline fallback. | Ensures evaluators can run the full prototype immediately even without a cloud API key or during transient API rate limits. |
| URL Shortener Persistence & Analytics | Uses persistent SQLite connections (:memory: / local file) with Base62 ID encoding and synchronous click tracking for standalone demoability. | Single-node storage; in production, this would scale horizontally using PostgreSQL (durable storage), Redis (sub-10ms redirect cache), and an async queue (Kafka/RabbitMQ) for analytics ingestion. |

6. Known Limitations & Future Production Enhancements

• AST-Level Brownfield Indexing: The current Codebase Reasoner inspects a structured repository metadata graph. Integrating tree-sitter would enable symbol-level AST dependency extraction across large multi-service repositories.
• Containerized Execution Sandbox: Replacing tempfile.TemporaryDirectory() with ephemeral Docker containers or microVMs (e.g., E2B) would provide full network and filesystem isolation when executing untrusted generated code.
• Direct Git PR Automation: Adding a final publisher node using the GitHub API would automatically open a draft Pull Request containing code diffs, pytest logs, and the risk assessment report.
