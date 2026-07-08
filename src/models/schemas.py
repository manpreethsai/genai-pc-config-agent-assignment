"""Pydantic models for structured agent inputs and outputs."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ComponentCategory(str, Enum):
    CPU = "cpu"
    MOTHERBOARD = "motherboard"
    MEMORY = "memory"
    VIDEO_CARD = "video_card"
    POWER_SUPPLY = "power_supply"
    CASE = "case"
    INTERNAL_HARD_DRIVE = "internal_hard_drive"
    CPU_COOLER = "cpu_cooler"


class UserRequirements(BaseModel):
    usage: str = Field(description="Primary use case, e.g. gaming, office, video editing")
    budget_usd: Optional[float] = Field(default=None, ge=0)
    preferences: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

    @field_validator("usage")
    @classmethod
    def usage_not_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("usage must not be empty")
        return cleaned


class ComponentSelection(BaseModel):
    category: ComponentCategory
    name: str
    price: float
    rationale: Optional[str] = None


class PCBuild(BaseModel):
    components: List[ComponentSelection]
    total_price: float
    summary: str
    compatibility_notes: List[str] = Field(default_factory=list)
    tradeoffs: List[str] = Field(default_factory=list)
    feasible: bool = True
    infeasibility_reason: Optional[str] = None


class AgentStepType(str, Enum):
    REASON = "reason"
    PLAN = "plan"
    ACT = "act"
    OBSERVE = "observe"
    RESPOND = "respond"
    CRITIQUE = "critique"


class AgentStep(BaseModel):
    step_type: AgentStepType
    content: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Dict[str, Any]] = None


class AgentTrace(BaseModel):
    session_id: str
    user_input: str
    requirements: Optional[UserRequirements] = None
    steps: List[AgentStep] = Field(default_factory=list)
    final_build: Optional[PCBuild] = None
    errors: List[str] = Field(default_factory=list)


class ComponentQueryParams(BaseModel):
    category: ComponentCategory
    max_price: Optional[float] = None
    min_price: Optional[float] = None
    socket: Optional[str] = None
    form_factor: Optional[str] = None
    brand_preference: Optional[str] = None
    keyword: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=50)


class CompatibilityCheckRequest(BaseModel):
    components: List[ComponentSelection]


class CompatibilityResult(BaseModel):
    compatible: bool
    issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    estimated_psu_watts: Optional[int] = None
