"""Evaluation scenarios and runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.agent.loop import PCConfigAgent
from src.evaluation.report import write_agent_run_report, write_custom_run_report
from src.config import settings


@dataclass(frozen=True)
class Scenario:
    name: str
    user_input: str
    feedback: str | None
    expected: list[str]


SCENARIOS: list[Scenario] = [
    Scenario(
        name="budget_office",
        user_input="I need a $600 PC for web browsing and school work.",
        feedback=None,
        expected=[
            "feasible",
            "within_budget",
            "has_cpu",
            "has_motherboard",
            "has_memory",
        ],
    ),
    Scenario(
        name="gaming_amd",
        user_input="Build me a 1440p gaming PC around $1500. I prefer AMD.",
        feedback=None,
        expected=["feasible", "has_gpu", "amd_preference"],
    ),
    Scenario(
        name="infeasible_flagship_gpu",
        user_input="I want an RTX 4090 build for $800 total.",
        feedback=None,
        expected=["infeasible"],
    ),
    Scenario(
        name="feedback_cheaper_gpu",
        user_input="Gaming PC around $1400 for 1440p.",
        feedback="Please make the GPU cheaper.",
        expected=["feasible", "feedback_applied"],
    ),
    Scenario(
        name="content_creation",
        user_input="Video editing workstation with 32GB RAM, budget $1800.",
        feedback=None,
        expected=["feasible", "has_storage"],
    ),
]


def evaluate_trace(trace, scenario: Scenario) -> dict[str, object]:
    build = trace.final_build
    checks: dict[str, bool] = {}

    checks["feasible"] = bool(build and build.feasible)
    checks["infeasible"] = bool(build and not build.feasible)
    checks["within_budget"] = bool(
        build
        and trace.requirements
        and trace.requirements.budget_usd is not None
        and build.total_price <= trace.requirements.budget_usd * 1.05
    )

    categories = {component.category.value for component in build.components} if build else set()
    checks["has_cpu"] = "cpu" in categories
    checks["has_motherboard"] = "motherboard" in categories
    checks["has_memory"] = "memory" in categories
    checks["has_gpu"] = "video_card" in categories
    checks["has_storage"] = "internal_hard_drive" in categories

    names = " ".join(component.name.lower() for component in build.components) if build else ""
    checks["amd_preference"] = "ryzen" in names or "radeon" in names
    checks["feedback_applied"] = any(
        step.tool_name == "query_components" and "budget feedback" in step.content.lower()
        for step in trace.steps
    ) or any("feedback" in note.lower() for note in (build.tradeoffs if build else []))

    expected_results = {item: checks.get(item, False) for item in scenario.expected}
    passed = all(expected_results.values())

    return {
        "scenario": scenario.name,
        "passed": passed,
        "checks": expected_results,
        "total_price": build.total_price if build else None,
        "component_count": len(build.components) if build else 0,
        "session_id": trace.session_id,
    }


def run_evaluation() -> list[dict[str, object]]:
    agent = PCConfigAgent()
    results: list[dict[str, object]] = []
    report_trace = None

    for scenario in SCENARIOS:
        trace = agent.run(scenario.user_input, prior_feedback=scenario.feedback)
        result = evaluate_trace(trace, scenario)
        results.append(result)

        if scenario.name == "gaming_amd":
            report_trace = trace

    if report_trace:
        write_agent_run_report(
            report_trace,
            results,
            Path(__file__).resolve().parent.parent.parent / "AGENT_RUN_REPORT.md",
        )

    return results


def run_recent_runs_report(limit: int = 5) -> None:
    """Generate a report from the most recent custom trace files.
    
    Updates AGENT_RUN_REPORT.md with the most recent run as primary
    and N recent traces as context.
    
    Args:
        limit: Number of recent traces to include in the report
    """
    logs_dir = Path(settings.log_dir)
    output_path = Path(__file__).resolve().parent.parent.parent / "AGENT_RUN_REPORT.md"
    
    if not logs_dir.exists():
        print(f"Logs directory not found: {logs_dir}")
        return
    
    trace_files = sorted(logs_dir.glob("trace_*.json"), reverse=True)
    if not trace_files:
        print(f"No trace files found in {logs_dir}")
        return
    
    import json
    from src.models.schemas import AgentTrace
    
    primary_trace_file = trace_files[0]
    with open(primary_trace_file) as f:
        trace_data = json.load(f)
        primary_trace = AgentTrace(**trace_data)
    
    write_custom_run_report(primary_trace, logs_dir, output_path, limit=limit)
