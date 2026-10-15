from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

Mode = Literal["quick", "standard", "deep", "audit", "plan", "implement"]

class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace: str = Field(min_length=1, max_length=4096)
    task: str = Field(min_length=1, max_length=30000)
    mode: Mode = "standard"
    pack: str = "software-development"
    max_iterations: int = Field(default=3, ge=1, le=10)
    max_agent_calls: int = Field(default=15, ge=1, le=100)
    max_total_tokens: int | None = Field(default=None, ge=1, le=10**12)
    max_parallel_agents: int = Field(default=2, ge=1, le=4)
    max_run_duration: int = Field(default=1800, ge=30, le=86400)
    auto_commit: bool = False
    isolated: bool = True
    specialists: list[str] = Field(default_factory=list, max_length=8)

class AgentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    role: str = Field(min_length=1, max_length=100)
    instructions: str = Field(min_length=1, max_length=20000)
    permission: Literal["read-only", "workspace-write"] = "read-only"
    model: str | None = Field(default=None, max_length=128)
    reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"] | None = None
    enabled: bool = True
    description: str = Field(default="", max_length=1000)
    enabled_modes: list[Mode] = Field(default_factory=lambda: ["quick", "standard", "deep", "audit", "plan", "implement"])
    can_execute: bool = True
    can_network: bool = False
    builtin: bool = Field(default=False, exclude=True)
    confirmed_permissions: bool = Field(default=False, exclude=True)


class AgentPack(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    title: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=1000)
    default_mode: Mode = "standard"
    agents: list[str] = Field(default_factory=list, max_length=32)
    specialists: list[str] = Field(default_factory=list, max_length=8)
    builtin: bool = Field(default=False, exclude=True)

    @field_validator("agents", "specialists")
    @classmethod
    def identifiers(cls, values):
        import re
        if any(not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value) for value in values):
            raise ValueError("Agent identifiers must use lowercase letters, digits, hyphens or underscores")
        if len(values) != len(set(values)):
            raise ValueError("Agent identifiers cannot be repeated")
        return values

class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    severity: Literal["critical", "high", "medium", "low"]
    file: str
    problem: str
    evidence: str
    expected_behavior: str
    suggested_fix: str

class TestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command: str
    exit_code: int | None
    output: str

class ProjectMap(BaseModel):
    model_config = ConfigDict(extra="forbid")
    modules: list[str]
    entry_points: list[str]
    important_files: list[str]
    dependencies: list[str]
    tests: list[str]
    build_commands: list[str]
    runtime_commands: list[str]
    architecture_notes: list[str]

class AgentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Literal["PLAN", "ANALYSIS", "IMPLEMENTED", "PASS", "FAIL", "APPROVED", "CHANGES_REQUIRED", "USER_DECISION_REQUIRED"]
    summary: str
    plan: list[str]
    acceptance_criteria: list[str]
    relevant_files: list[str]
    build_commands: list[str]
    tests: list[TestResult]
    findings: list[Finding]
    assumptions: list[str]
    specialists: list[str]
    project_map: ProjectMap

EXPECTED = {"coordinator": {"PLAN", "USER_DECISION_REQUIRED"}, "analyst": {"ANALYSIS", "USER_DECISION_REQUIRED"},
            "developer": {"IMPLEMENTED", "USER_DECISION_REQUIRED"}, "qa": {"PASS", "FAIL", "USER_DECISION_REQUIRED"},
            "reviewer": {"APPROVED", "CHANGES_REQUIRED", "USER_DECISION_REQUIRED"},
            "architect": {"PLAN", "USER_DECISION_REQUIRED"}, "final-audit": {"APPROVED", "CHANGES_REQUIRED", "USER_DECISION_REQUIRED"}}

def parse_result(text: str, role: str) -> dict:
    # Strict JSON: don't silently salvage arbitrary malformed agent output.
    result = AgentResult.model_validate_json(text)
    allowed = EXPECTED.get(role, {"ANALYSIS", "PASS", "FAIL", "APPROVED", "CHANGES_REQUIRED", "USER_DECISION_REQUIRED"})
    if result.verdict not in allowed:
        raise ValueError(f"Unexpected verdict {result.verdict} from {role}")
    if result.verdict in {"FAIL", "CHANGES_REQUIRED"} and not result.findings:
        raise ValueError("Rejected result must contain evidence-backed findings")
    return result.model_dump()
