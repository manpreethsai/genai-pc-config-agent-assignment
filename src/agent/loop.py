"""Agent loop: reason -> plan -> act -> observe -> respond."""

from __future__ import annotations

import json
from typing import Any

from src.agent.llm_client import LLMClient
from src.agent.planner import BuildPlanner
from src.config import settings
from src.data.loader import ComponentRepository
from src.guardrails.validation import estimate_tokens, validate_user_input
from src.logging.trace import TraceLogger
from src.models.schemas import (
    AgentStep,
    AgentStepType,
    AgentTrace,
    CompatibilityCheckRequest,
    ComponentQueryParams,
    PCBuild,
    UserRequirements,
)
from src.tools.compatibility import CompatibilityTool
from src.tools.component_query import ComponentQueryTool


class PCConfigAgent:
    """Orchestrates requirement gathering, tool calls, critique, and response."""

    def __init__(self) -> None:
        self.settings = settings
        self.repository = ComponentRepository()
        self.query_tool = ComponentQueryTool(self.repository)
        self.compat_tool = CompatibilityTool(self.repository)
        self.planner = BuildPlanner(self.repository)
        self.llm = LLMClient(self.settings)
        self.trace_logger = TraceLogger()

    def run(self, user_input: str, prior_feedback: str | None = None) -> AgentTrace:
        combined_input = user_input if not prior_feedback else f"{user_input}\nFeedback: {prior_feedback}"
        trace = self.trace_logger.new_trace(combined_input)

        valid, message = validate_user_input(combined_input, self.settings.max_input_chars)
        if not valid:
            trace.errors.append(message)
            self.trace_logger.add_step(
                trace,
                AgentStep(step_type=AgentStepType.RESPOND, content=message),
            )
            self.trace_logger.save(trace)
            return trace

        if estimate_tokens(combined_input) > self.settings.max_tokens:
            trace.errors.append("Input is too long after token estimation.")
            self.trace_logger.add_step(
                trace,
                AgentStep(step_type=AgentStepType.RESPOND, content="Input too long; please shorten your request."),
            )
            self.trace_logger.save(trace)
            return trace

        self.trace_logger.add_step(
            trace,
            AgentStep(
                step_type=AgentStepType.REASON,
                content="Interpreting user goals, budget, preferences, and constraints.",
            ),
        )

        try:
            requirements_payload = self.llm.extract_requirements(combined_input)
            requirements = UserRequirements(**requirements_payload)
            trace.requirements = requirements
        except Exception as exc:  # noqa: BLE001
            trace.errors.append(f"Requirement extraction failed: {exc}")
            requirements = UserRequirements(usage="general", budget_usd=None)

        self.trace_logger.add_step(
            trace,
            AgentStep(
                step_type=AgentStepType.PLAN,
                content=f"Planning component queries for usage={requirements.usage}, budget={requirements.budget_usd}.",
            ),
        )

        build, tool_events = self.planner.plan(requirements)

        for event in tool_events:
            self.trace_logger.add_step(
                trace,
                AgentStep(
                    step_type=AgentStepType.ACT,
                    content=f"Executed tool `{event['tool']}`.",
                    tool_name=event["tool"],
                    tool_input=event.get("input"),
                    tool_output=event.get("output"),
                ),
            )
            self.trace_logger.add_step(
                trace,
                AgentStep(
                    step_type=AgentStepType.OBSERVE,
                    content="Processed tool output and updated build draft.",
                    tool_name=event["tool"],
                    tool_output=event.get("output"),
                ),
            )

        critique: dict[str, Any] = {}
        try:
            critique = self.llm.self_critique(build.model_dump(), requirements.model_dump())
            self.trace_logger.add_step(
                trace,
                AgentStep(
                    step_type=AgentStepType.CRITIQUE,
                    content=json.dumps(critique),
                ),
            )
            if critique.get("issues"):
                build.tradeoffs.extend(str(item) for item in critique["issues"])
            if critique.get("approved") is False and build.feasible:
                build.feasible = False
                build.infeasibility_reason = "; ".join(str(item) for item in critique.get("issues", []))
        except Exception as exc:  # noqa: BLE001
            trace.errors.append(f"Self-critique failed: {exc}")

        if prior_feedback:
            build = self._apply_feedback(build, prior_feedback, trace)

        trace.final_build = build
        self.trace_logger.add_step(
            trace,
            AgentStep(
                step_type=AgentStepType.RESPOND,
                content=build.summary,
            ),
        )
        self.trace_logger.save(trace)
        return trace

    def _apply_feedback(self, build: PCBuild, feedback: str, trace: AgentTrace) -> PCBuild:
        lowered = feedback.lower()
        if not build.components:
            return build

        if "cheaper" in lowered or "lower" in lowered or "budget" in lowered:
            for component in build.components:
                if component.category.value == "video_card":
                    query = ComponentQueryParams(
                        category=component.category,
                        max_price=max(component.price * 0.7, 120),
                        limit=5,
                    )
                    result = self.query_tool.query(query)
                    self.trace_logger.add_step(
                        trace,
                        AgentStep(
                            step_type=AgentStepType.ACT,
                            content="Re-querying GPU after budget feedback.",
                            tool_name="query_components",
                            tool_input=query.model_dump(),
                            tool_output=result,
                        ),
                    )
                    if result["results"]:
                        replacement = result["results"][0]
                        old_price = component.price
                        component.name = replacement["name"]
                        component.price = float(replacement["price"])
                        component.rationale = "Adjusted GPU based on user budget feedback."
                        build.total_price = round(build.total_price - old_price + component.price, 2)
                        build.tradeoffs.append("GPU downgraded per user feedback.")
                    break

        compat = self.compat_tool.validate(CompatibilityCheckRequest(components=build.components))
        build.compatibility_notes = compat.warnings
        if not compat.compatible:
            build.feasible = False
            build.infeasibility_reason = "; ".join(compat.issues)
        build.summary = f"{build.summary} Revised after user feedback."
        return build
