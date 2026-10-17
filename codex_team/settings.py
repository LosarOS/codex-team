"""Validated partial settings. Provider selection has its own explicit endpoint."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .models import AgentSpec

Effort = Literal["none","minimal","low","medium","high","xhigh","max","ultra"]
PermissionCategory = Literal["file_access","command_execution","package_installation","network_access","git_operations","external_tools","project_writes"]


class Notifications(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_complete: bool = True
    needs_attention: bool = True
    stage_complete: bool = False


class RoleDefault(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str | None = Field(default=None,max_length=128)
    reasoning_effort: Effort | None = None


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    execution_backend: str | None = None
    model: str | None = Field(default=None,max_length=128)
    reasoning_effort: Effort | None = None
    max_iterations: int = Field(default=3,ge=1,le=10)
    max_agent_calls: int = Field(default=15,ge=1,le=100)
    max_parallel_agents: int = Field(default=2,ge=1,le=4)
    max_run_duration: int = Field(default=1800,ge=30,le=86400)
    # Existing identifiers remain valid for preferences saved by older releases.
    theme: Literal["system","light","dark","purple-neon","dark-fantasy",
                   "obsidian-violet","neon-blue","emerald-tech","crimson-night"] = "obsidian-violet"
    language: Literal["ru","en"] = "ru"
    accent_color: str | None = Field(default=None,pattern=r"^#[0-9a-fA-F]{6}$")
    notifications: Notifications = Field(default_factory=Notifications)
    permission_policy: dict[PermissionCategory,Literal["ask","deny"]] = Field(default_factory=dict)
    minimize_to_tray: bool = False
    role_model_defaults: dict[str,RoleDefault] = Field(default_factory=dict)
    onboarding_dismissed: bool = False

    @field_validator("role_model_defaults")
    @classmethod
    def bounded_roles(cls, values):
        import re
        if len(values)>64 or any(not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}",key) for key in values):
            raise ValueError("Role defaults must use valid agent identifiers")
        return values
