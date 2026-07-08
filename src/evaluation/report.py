"""Generate the Agent Run Report markdown document."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from src.logging.trace import TraceLogger
from src.models.schemas import AgentTrace


ARCHITECTURE_SECTION = """## Architecture Overview

```mermaid
flowchart TB
    subgraph input [Input Layer]
        User[User Requirements]
        Feedback[User Feedback]
    end

    subgraph guardrails [Guardrails]
        Validate[Input Validation]
        TokenCheck[Token Limit Check]
    end

    subgraph agent [Agent Loop]
        Reason[REASON]
        Plan[PLAN]
        Act[ACT - Tool Calls]
        Observe[OBSERVE]
        Critique[CRITIQUE - Self Reflection]
        Respond[RESPOND]
    end

    subgraph tools [Tools]
        QueryTool[query_components]
        CompatTool[validate_compatibility]
    end

    subgraph data [Data Layer]
        Dataset[CSV Component Repository]
    end

    subgraph output [Output]
        Build[Structured PCBuild JSON]
        Trace[Agent Trace Logs]
    end

    User --> Validate
    Feedback --> Validate
    Validate --> TokenCheck
    TokenCheck --> Reason
    Reason --> Plan
    Plan --> Act
    Act --> QueryTool
    Act --> CompatTool
    QueryTool --> Dataset
    CompatTool --> Dataset
    QueryTool --> Observe
    CompatTool --> Observe
    Observe --> Critique
    Critique --> Respond
    Respond --> Build
    agent --> Trace
```

### Agent Goal

Assist users in configuring a **compatible, budget-aware PC build** using only components from the provided dataset.

### Available Tools

| Tool | Purpose |
|------|---------|
| `query_components` | Filter dataset by category, price, socket, form factor, brand, keyword |
| `validate_compatibility` | Check socket match, memory generation, PSU wattage, GPU clearance |

### Advanced Techniques Used

- **Chain-of-thought prompting** — system prompt instructs internal reasoning before tool use
- **Self-critique** — draft build is reviewed for budget/compatibility before responding
- **Structured output** — Pydantic models (`PCBuild`, `UserRequirements`, `AgentTrace`)
"""

DESIGN_DECISIONS = """## Design Decisions and Trade-offs

### Custom agent loop vs. LangChain/LangGraph

A lightweight custom loop was chosen to keep the project readable and demonstrate direct control over the `reason → plan → act → observe → respond` flow. LangGraph would add value for multi-agent orchestration but increases setup complexity for a focused assessment.

### Deterministic planner + LLM layer

The LLM handles requirement extraction and self-critique. Component selection uses a **deterministic planner** that queries the dataset via tools. This prevents hallucinated SKUs and keeps builds reproducible for evaluation. Trade-off: the planner is heuristic, not globally optimal.

### Mock LLM mode

`USE_MOCK_LLM=true` enables full end-to-end runs without API keys. Useful for CI and graders. Live mode uses OpenAI with retries, timeouts, and JSON response format.

### Compatibility validation in code

Compatibility rules (socket, DDR generation, PSU estimate, GPU length warnings) are implemented in Python rather than left to the LLM. This improves correctness and provides inspectable validation output.

### Dataset socket inference

CPUs in the dataset lack explicit socket columns. Socket is inferred from microarchitecture and product name heuristics. This is imperfect for legacy parts but sufficient for modern builds.

### Known limitations

- Budget allocation is heuristic; builds may under-spend on high budgets
- No RAG embedding index (dataset filtering is structured query, not semantic search)
- Single-turn feedback revision (not full multi-session memory)
"""


def write_agent_run_report(
    trace: AgentTrace,
    evaluation_results: list[dict[str, object]],
    output_path: Path,
) -> None:
    logger = TraceLogger()
    sections = [
        "# GenAI PC Configuration Agent — Run Report",
        "",
        ARCHITECTURE_SECTION,
        "",
        DESIGN_DECISIONS,
        "",
        "## Evaluation Summary",
        "",
        "| Scenario | Passed | Total Price | Components |",
        "|----------|--------|-------------|------------|",
    ]

    for result in evaluation_results:
        sections.append(
            f"| {result['scenario']} | {'Yes' if result['passed'] else 'No'} | "
            f"${result.get('total_price', 'N/A')} | {result.get('component_count', 0)} |"
        )

    passed = sum(1 for r in evaluation_results if r["passed"])
    sections.extend(
        [
            "",
            f"**Result:** {passed}/{len(evaluation_results)} scenarios passed.",
            "",
            "## Representative Test Scenarios",
            "",
            "1. **Budget office** — $600 web/school PC stays feasible and within budget",
            "2. **Gaming AMD** — 1440p gaming with AMD preference includes GPU and Ryzen/Radeon parts",
            "3. **Infeasible flagship** — RTX 4090 at $800 is rejected with explanation",
            "4. **Feedback loop** — User asks for cheaper GPU; agent re-queries and revises",
            "5. **Content creation** — Video editing workstation includes storage",
            "",
            "---",
            "",
            "## Full Agent Trace (Gaming AMD Scenario)",
            "",
            logger.render_markdown(trace),
        ]
    )

    output_path.write_text("\n".join(sections), encoding="utf-8")


def write_custom_run_report(
    trace: AgentTrace,
    logs_dir: Path,
    output_path: Path,
    limit: int = 5,
) -> None:
    """Generate a report from custom user runs (non-evaluation traces).
    
    Includes the primary trace + N most recent related traces for context.
    
    Args:
        trace: The primary trace to feature in the report
        logs_dir: Directory containing trace JSON files
        output_path: Path to write the markdown report (AGENT_RUN_REPORT.md)
        limit: Number of total recent traces to include
    """
    logger = TraceLogger()
    
    trace_files = sorted(logs_dir.glob("trace_*.json"), reverse=True)[:limit]
    
    if not trace_files:
        print(f"No trace files found in {logs_dir}")
        return
    
    sections = [
        "# GenAI PC Configuration Agent — Run Report",
        "",
        ARCHITECTURE_SECTION,
        "",
        DESIGN_DECISIONS,
        "",
        f"## Custom Run Report ({len(trace_files)} recent traces)",
        "",
        "| # | Total Price | Components | Feasible | Input |",
        "|---|-------------|------------|----------|-------|",
    ]
    
    traces: list[AgentTrace] = []
    for idx, trace_file in enumerate(trace_files, 1):
        try:
            with open(trace_file) as f:
                trace_data = json.load(f)
                loaded_trace = AgentTrace(**trace_data)
                traces.append(loaded_trace)
                
                build = loaded_trace.final_build
                feasible = "✓ Yes" if (build and build.feasible) else "✗ No"
                total_price = f"${build.total_price}" if build else "N/A"
                component_count = len(build.components) if build else 0
                user_input = loaded_trace.user_input[:50] + "..." if len(loaded_trace.user_input) > 50 else loaded_trace.user_input
                
                sections.append(
                    f"| {idx} | {total_price} | {component_count} | {feasible} | {user_input} |"
                )
        except Exception as e:
            print(f"Error loading trace {trace_file}: {e}")
            continue
    
    sections.extend([
        "",
        "---",
        "",
        "## Primary Run Trace",
        "",
        logger.render_markdown(trace),
    ])
    
    output_path.write_text("\n".join(sections), encoding="utf-8")
    print(f"✓ Report updated: {output_path}")
