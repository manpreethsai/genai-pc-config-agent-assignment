"""Structured trace logging for agent observability."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.config import settings
from src.models.schemas import AgentStep, AgentTrace


class TraceLogger:
    """Persist agent reasoning steps for inspection."""

    def __init__(self, log_dir: Path | None = None) -> None:
        self.log_dir = log_dir or settings.log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def new_trace(self, user_input: str) -> AgentTrace:
        return AgentTrace(session_id=str(uuid.uuid4()), user_input=user_input)

    def add_step(self, trace: AgentTrace, step: AgentStep) -> None:
        trace.steps.append(step)

    def save(self, trace: AgentTrace) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        file_path = self.log_dir / f"trace_{timestamp}_{trace.session_id}.json"
        file_path.write_text(trace.model_dump_json(indent=2), encoding="utf-8")
        return file_path

    def render_markdown(self, trace: AgentTrace) -> str:
        lines = [
            f"# Agent Trace `{trace.session_id}`",
            "",
            f"**User input:** {trace.user_input}",
            "",
            "## Steps",
        ]
        for index, step in enumerate(trace.steps, start=1):
            lines.append(f"### {index}. {step.step_type.value.upper()}")
            lines.append(step.content)
            if step.tool_name:
                lines.append(f"- Tool: `{step.tool_name}`")
            if step.tool_input:
                lines.append(f"- Input: `{json.dumps(step.tool_input)}`")
            if step.tool_output:
                lines.append(f"- Output: `{json.dumps(step.tool_output)[:1200]}`")
            lines.append("")

        if trace.final_build:
            lines.extend(["## Final Build", "```json", trace.final_build.model_dump_json(indent=2), "```"])

        if trace.errors:
            lines.extend(["## Errors", *[f"- {err}" for err in trace.errors]])

        return "\n".join(lines)
