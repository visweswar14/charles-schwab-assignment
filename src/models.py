from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ScenarioType(Enum):
    GREENFIELD = "greenfield"
    BROWNFIELD = "brownfield"
    TEST_DOCS = "test_docs"


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskNode:
    id: str
    title: str
    agent_role: str
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    output: Optional[str] = None
    retries: int = 0


@dataclass
class EngineeringState:
    raw_requirement: str
    repo_context: Optional[Dict[str, Any]] = None
    scenario: Optional[ScenarioType] = None
    normalized_spec: Optional[Dict[str, Any]] = None
    ambiguities: List[str] = field(default_factory=list)
    impact_analysis: Optional[Dict[str, Any]] = None
    task_dag: Dict[str, TaskNode] = field(default_factory=dict)
    plan_rationale: str = ""
    artifacts: Dict[str, str] = field(default_factory=dict)
    risk_report: Dict[str, Any] = field(default_factory=dict)
    assumptions_and_limitations: List[str] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    iteration_count: int = 0
    human_approved: bool = False
