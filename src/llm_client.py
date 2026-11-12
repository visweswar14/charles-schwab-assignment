import os
import time
from typing import List
from google import genai
from google.genai import types
from google.genai.errors import ServerError
from pydantic import BaseModel
from src.offline_fallback import get_offline_response


class NormalizedSpecSchema(BaseModel):
    goal: str
    constraints: List[str]
    acceptance_criteria: List[str]


class IntakeResponseSchema(BaseModel):
    is_ambiguous: bool
    ambiguities: List[str]
    scenario: str
    normalized: NormalizedSpecSchema


class ImpactAnalysisSchema(BaseModel):
    impacted_files: List[str]
    affected_apis: List[str]
    data_flow: str


class TaskItemSchema(BaseModel):
    id: str
    title: str
    role: str
    deps: List[str]


SYSTEM_PROMPTS = {
    "intake": (
        "You are a Principal Software Architect triaging incoming requirements. "
        "Classify the scenario as 'greenfield', 'brownfield', or 'test_docs'. "
        "If key details (metrics, target endpoints, expected behavior, or rules) are missing, "
        "set is_ambiguous=True and list specific clarifying questions. "
        "If clarification details are already provided in the prompt, set is_ambiguous=False."
    ),
    "codebase_reasoner": (
        "You are a Staff Engineer analyzing an existing codebase. "
        "Identify which files and APIs are impacted and trace the end-to-end data flow."
    ),
    "decomposer": (
        "You are an Engineering Manager breaking a spec into a Directed Acyclic Graph (DAG) of tasks. "
        "Create EXACTLY 4 tasks (strictly one per role): 'architect', 'developer', 'qa', and 'tech_writer'. "
        "Sequence: 'architect' first, then 'developer' (implements the complete standalone module), "
        "then 'qa' (depends on 'developer'), and 'tech_writer' last."
    ),
    "architect": (
        "You are an API & Systems Architect. Output ONLY valid OpenAPI 3.0 YAML or schema definitions. "
        "Do not include markdown code fences or conversational text."
    ),
    "developer": (
        "You are a Senior Backend Developer writing Python 3.9 compatible code. "
        "IMPORTANT: Do NOT use Python 3.10+ union syntax like 'dict | str' or 'int | None'; "
        "always use 'typing.Optional', 'typing.Union', 'typing.Dict', 'typing.Tuple'. "
        "Write a complete, self-contained Python service class using standard library (sqlite3, string, time, urllib.parse) "
        "without FastAPI/Flask web decorators. "
        "CRITICAL SQLITE RULE: Store a persistent connection 'self.conn = sqlite3.connect(db_path, check_same_thread=False)' in __init__, "
        "run 'CREATE TABLE IF NOT EXISTS ...' on self.conn inside __init__, and reuse self.conn in all methods (NEVER call sqlite3.connect() inside individual methods, because ':memory:' loses tables across separate connections). "
        "Always include try/except blocks around all database and I/O operations. "
        "Output ONLY raw Python code without markdown backticks."
    ),
    "qa": (
        "You are a QA Automation Engineer writing Python 3.9 compatible pytest unit tests. "
        "IMPORTANT: Inspect the provided 'Existing Developer Code to Test' and import ONLY the exact class/function names "
        "defined in it from 'solution'. Do NOT use 'dict | str' syntax. "
        "Include standalone pytest fixtures using ':memory:' SQLite. "
        "Output ONLY raw Python code without markdown backticks."
    ),
    "tech_writer": (
        "You are a Technical Writer. Write concise, clear Markdown documentation covering "
        "architecture decisions, usage examples, and failure modes."
    )
}

SCHEMA_MAP = {
    "intake": IntakeResponseSchema,
    "codebase_reasoner": ImpactAnalysisSchema,
    "decomposer": list[TaskItemSchema],
}


class LLMClient:
    def __init__(self, primary_model: str = "gemini-3.5-flash-lite"):
        self.models = [primary_model, "gemini-3.1-flash-lite-preview", "gemini-3.8-flash"]
        api_key = os.environ.get("GEMINI_API_KEY")

        if api_key and api_key != "your_gemini_api_key_here":
            self.client = genai.Client()
            self.offline_mode = False
        else:
            print("[!] GEMINI_API_KEY not set. Running in Offline Demo Mode.")
            self.client = None
            self.offline_mode = True

    def call(self, role: str, prompt: str) -> str:
        if self.offline_mode:
            return get_offline_response(role, prompt)

        time.sleep(4)  # Stay safely under Free Tier 15 RPM rate limit

        config_args = {
            "system_instruction": SYSTEM_PROMPTS.get(role, "You are a helpful software engineering agent."),
            "temperature": 0.2,
        }

        if role in SCHEMA_MAP:
            config_args["response_mime_type"] = "application/json"
            config_args["response_schema"] = SCHEMA_MAP[role]

        for model_name in self.models:
            for _ in range(2):
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(**config_args),
                    )
                    return response.text
                except ServerError:
                    print(f"  [!] {model_name} busy (503). Retrying...")
                    time.sleep(1.5)
                except Exception as e:
                    print(f"  [!] Switching from {model_name}: {e}")
                    break

        print("  [!] Cloud models overloaded. Using Offline Simulator fallback.")
        return get_offline_response(role, prompt)
