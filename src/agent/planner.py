"""Deterministic build planner used by mock mode and as a fallback."""

from __future__ import annotations

from typing import Any

from src.data.loader import ComponentRepository
from src.models.schemas import (
    CompatibilityCheckRequest,
    ComponentCategory,
    ComponentQueryParams,
    ComponentSelection,
    PCBuild,
    UserRequirements,
)
from src.tools.compatibility import CompatibilityTool
from src.tools.component_query import ComponentQueryTool


class BuildPlanner:
    """Rule-based planner that queries the dataset and assembles a build."""

    def __init__(self, repository: ComponentRepository) -> None:
        self.query_tool = ComponentQueryTool(repository)
        self.compat_tool = CompatibilityTool(repository)

    @staticmethod
    def _pick_near_budget(results: list[dict[str, Any]], target_price: float) -> dict[str, Any] | None:
        candidates = [row for row in results if (row.get("price") or 0) <= target_price]
        if not candidates:
            return None
        return max(candidates, key=lambda row: row.get("price") or 0)

    def plan(self, requirements: UserRequirements) -> tuple[PCBuild, list[dict[str, Any]]]:
        tool_events: list[dict[str, Any]] = []
        budget = requirements.budget_usd
        usage = requirements.usage.lower()
        prefer_amd = any("amd" in pref.lower() for pref in requirements.preferences)
        prefer_nvidia = any("nvidia" in pref.lower() or "geforce" in pref.lower() for pref in requirements.preferences)
        needs_discrete_gpu = usage in {"gaming", "content_creation"} or "gaming" in usage
        notes_blob = " ".join(
            [requirements.notes or "", requirements.usage, *requirements.preferences, *requirements.constraints]
        ).lower()
        needs_32gb_ram = "32gb" in notes_blob.replace(" ", "") or "32 gb" in notes_blob

        if requirements.constraints and any("high_end_gpu_low_budget" in c for c in requirements.constraints):
            return (
                PCBuild(
                    components=[],
                    total_price=0,
                    summary="Requested GPU tier is not feasible at this budget.",
                    tradeoffs=["Increase budget or choose a lower-tier GPU."],
                    feasible=False,
                    infeasibility_reason="Flagship GPU class cannot fit in the stated budget using dataset prices.",
                ),
                tool_events,
            )

        if budget is not None and budget < 350:
            return (
                PCBuild(
                    components=[],
                    total_price=0,
                    summary="Budget is too low for a full desktop build in this dataset.",
                    tradeoffs=["Consider raising budget to at least $500 for a minimal build."],
                    feasible=False,
                    infeasibility_reason="Insufficient budget for required core components.",
                ),
                tool_events,
            )

        remaining = budget if budget is not None else 2000.0
        cpu_budget = min(remaining * (0.22 if needs_discrete_gpu else 0.35), 450 if budget and budget >= 1200 else 350)
        cpu_min = 150.0 if needs_discrete_gpu and budget and budget >= 900 else (
            80.0 if needs_discrete_gpu else None
        )
        if prefer_amd and needs_discrete_gpu and budget and budget >= 1000:
            cpu_keyword = "Ryzen 7"
        elif prefer_amd:
            cpu_keyword = "Ryzen"
        elif any("intel" in p.lower() for p in requirements.preferences):
            cpu_keyword = "Intel Core i5"
        else:
            cpu_keyword = None

        cpu_query = ComponentQueryParams(
            category=ComponentCategory.CPU,
            max_price=cpu_budget,
            min_price=cpu_min,
            keyword=cpu_keyword,
            limit=40,
        )
        cpu_result = self.query_tool.query(cpu_query)
        tool_events.append({"tool": "query_components", "input": cpu_query.model_dump(), "output": cpu_result})
        if not cpu_result["results"]:
            return self._infeasible("No CPU found within budget.", tool_events)

        cpu_pick = self._pick_near_budget(cpu_result["results"], cpu_budget)
        if not cpu_pick:
            return self._infeasible("No CPU found within budget.", tool_events)
        remaining -= float(cpu_pick["price"] or 0)
        socket = cpu_pick.get("socket") or "AM5"

        mb_query = ComponentQueryParams(
            category=ComponentCategory.MOTHERBOARD,
            max_price=min(remaining * 0.25, 220),
            socket=socket,
            limit=10,
        )
        mb_result = self.query_tool.query(mb_query)
        tool_events.append({"tool": "query_components", "input": mb_query.model_dump(), "output": mb_result})
        if not mb_result["results"]:
            return self._infeasible("No compatible motherboard found.", tool_events)
        mb_pick = self._pick_near_budget(mb_result["results"], min(remaining * 0.25, 220))
        if not mb_pick:
            return self._infeasible("No compatible motherboard found.", tool_events)
        remaining -= float(mb_pick["price"] or 0)

        mem_keyword = "32 GB" if needs_32gb_ram else ("DDR5" if socket in {"AM5", "LGA1700", "LGA1851"} else "DDR4")
        mem_budget = min(remaining * 0.15, 160 if needs_32gb_ram else 120)
        mem_min = 30.0 if needs_discrete_gpu or needs_32gb_ram else None
        mem_query = ComponentQueryParams(
            category=ComponentCategory.MEMORY,
            max_price=mem_budget,
            min_price=mem_min,
            keyword=mem_keyword,
            limit=20,
        )
        mem_result = self.query_tool.query(mem_query)
        tool_events.append({"tool": "query_components", "input": mem_query.model_dump(), "output": mem_result})
        if not mem_result["results"]:
            mem_query = ComponentQueryParams(
                category=ComponentCategory.MEMORY,
                max_price=min(remaining * 0.15, 120),
                limit=10,
            )
            mem_result = self.query_tool.query(mem_query)
            tool_events.append({"tool": "query_components", "input": mem_query.model_dump(), "output": mem_result})
        if not mem_result["results"]:
            return self._infeasible("No memory found within budget.", tool_events)
        mem_pick = self._pick_near_budget(mem_result["results"], min(remaining * 0.15, 120))
        if not mem_pick:
            return self._infeasible("No memory found within budget.", tool_events)
        remaining -= float(mem_pick["price"] or 0)

        components: list[ComponentSelection] = [
            ComponentSelection(category=ComponentCategory.CPU, name=cpu_pick["name"], price=float(cpu_pick["price"]), rationale="CPU matched to workload and budget"),
            ComponentSelection(category=ComponentCategory.MOTHERBOARD, name=mb_pick["name"], price=float(mb_pick["price"]), rationale=f"Motherboard with socket {socket}"),
            ComponentSelection(category=ComponentCategory.MEMORY, name=mem_pick["name"], price=float(mem_pick["price"]), rationale="Memory sized for target workload"),
        ]

        if needs_discrete_gpu:
            gpu_budget = min(remaining * 0.55, 900)
            if prefer_nvidia:
                gpu_keyword = "GeForce RTX"
                gpu_min = 200.0 if budget and budget >= 800 else 120.0
            elif prefer_amd:
                gpu_keyword = "Radeon RX"
                gpu_min = 200.0 if budget and budget >= 800 else 120.0
            else:
                gpu_keyword = "RTX"
                gpu_min = 180.0
            gpu_query = ComponentQueryParams(
                category=ComponentCategory.VIDEO_CARD,
                max_price=gpu_budget,
                min_price=gpu_min,
                keyword=gpu_keyword,
                limit=30,
            )
            gpu_result = self.query_tool.query(gpu_query)
            tool_events.append({"tool": "query_components", "input": gpu_query.model_dump(), "output": gpu_result})
            if gpu_result["results"]:
                gpu_pick = self._pick_near_budget(gpu_result["results"], gpu_budget)
                if gpu_pick:
                    components.append(
                        ComponentSelection(
                            category=ComponentCategory.VIDEO_CARD,
                            name=gpu_pick["name"],
                            price=float(gpu_pick["price"]),
                            rationale="Discrete GPU for gaming/content workloads",
                        )
                    )
                    remaining -= float(gpu_pick["price"] or 0)

        storage_query = ComponentQueryParams(
            category=ComponentCategory.INTERNAL_HARD_DRIVE,
            max_price=min(remaining * 0.2, 120),
            keyword="SSD",
            limit=8,
        )
        storage_result = self.query_tool.query(storage_query)
        tool_events.append({"tool": "query_components", "input": storage_query.model_dump(), "output": storage_result})
        if storage_result["results"]:
            storage_pick = self._pick_near_budget(storage_result["results"], min(remaining * 0.2, 120))
            if storage_pick:
                components.append(
                    ComponentSelection(
                        category=ComponentCategory.INTERNAL_HARD_DRIVE,
                        name=storage_pick["name"],
                        price=float(storage_pick["price"]),
                        rationale="Primary SSD storage",
                    )
                )
                remaining -= float(storage_pick["price"] or 0)

        psu_query = ComponentQueryParams(
            category=ComponentCategory.POWER_SUPPLY,
            max_price=min(remaining * 0.25, 140),
            keyword="650" if needs_discrete_gpu else None,
            limit=10,
        )
        psu_result = self.query_tool.query(psu_query)
        tool_events.append({"tool": "query_components", "input": psu_query.model_dump(), "output": psu_result})
        if psu_result["results"]:
            psu_pick = self._pick_near_budget(psu_result["results"], min(remaining * 0.25, 140))
            if psu_pick:
                components.append(
                    ComponentSelection(
                        category=ComponentCategory.POWER_SUPPLY,
                        name=psu_pick["name"],
                        price=float(psu_pick["price"]),
                        rationale="PSU with adequate wattage",
                    )
                )
                remaining -= float(psu_pick["price"] or 0)

        case_query = ComponentQueryParams(
            category=ComponentCategory.CASE,
            max_price=min(max(remaining, 50), 100),
            form_factor="ATX Mid Tower",
            limit=8,
        )
        case_result = self.query_tool.query(case_query)
        tool_events.append({"tool": "query_components", "input": case_query.model_dump(), "output": case_result})
        if case_result["results"]:
            case_pick = self._pick_near_budget(case_result["results"], min(max(remaining, 50), 100))
            if case_pick:
                components.append(
                    ComponentSelection(
                        category=ComponentCategory.CASE,
                        name=case_pick["name"],
                        price=float(case_pick["price"]),
                        rationale="ATX case compatible with standard builds",
                    )
                )

        compat = self.compat_tool.validate(CompatibilityCheckRequest(components=components))
        tool_events.append(
            {
                "tool": "validate_compatibility",
                "input": {"components": [c.model_dump() for c in components]},
                "output": compat.model_dump(),
            }
        )

        total_price = round(sum(component.price for component in components), 2)
        tradeoffs: list[str] = []
        if budget is not None and total_price > budget:
            tradeoffs.append(f"Build exceeds budget by ${round(total_price - budget, 2)}; consider cheaper GPU or CPU.")

        summary = (
            f"Configured a {requirements.usage} PC with {len(components)} core components "
            f"totaling ${total_price}."
        )

        return (
            PCBuild(
                components=components,
                total_price=total_price,
                summary=summary,
                compatibility_notes=compat.warnings,
                tradeoffs=tradeoffs,
                feasible=compat.compatible and (budget is None or total_price <= budget * 1.05),
                infeasibility_reason=None if compat.compatible else "; ".join(compat.issues),
            ),
            tool_events,
        )

    @staticmethod
    def _infeasible(reason: str, tool_events: list[dict[str, Any]]) -> tuple[PCBuild, list[dict[str, Any]]]:
        return (
            PCBuild(
                components=[],
                total_price=0,
                summary=reason,
                feasible=False,
                infeasibility_reason=reason,
            ),
            tool_events,
        )
