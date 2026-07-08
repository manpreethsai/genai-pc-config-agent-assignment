"""Compatibility validation tool for selected PC components."""

from __future__ import annotations

import re
from typing import Any

from src.data.loader import ComponentRepository, infer_memory_type
from src.models.schemas import CompatibilityCheckRequest, CompatibilityResult, ComponentSelection


def _category_value(category: str) -> str:
    return category.replace("-", "_")


class CompatibilityTool:
    """Validate conceptual compatibility across a proposed build."""

    def __init__(self, repository: ComponentRepository) -> None:
        self.repository = repository

    def _lookup(self, selection: ComponentSelection) -> dict[str, Any] | None:
        category = selection.category.value
        row = self.repository.find_by_name(category, selection.name)
        if row:
            return row
        return None

    def validate(self, request: CompatibilityCheckRequest) -> CompatibilityResult:
        issues: list[str] = []
        warnings: list[str] = []

        by_category: dict[str, ComponentSelection] = {}
        for component in request.components:
            by_category[component.category.value] = component

        cpu_row = self._lookup(by_category["cpu"]) if "cpu" in by_category else None
        mb_row = self._lookup(by_category["motherboard"]) if "motherboard" in by_category else None
        mem_row = self._lookup(by_category["memory"]) if "memory" in by_category else None
        gpu_row = self._lookup(by_category["video_card"]) if "video_card" in by_category else None
        psu_row = self._lookup(by_category["power_supply"]) if "power_supply" in by_category else None
        case_row = self._lookup(by_category["case"]) if "case" in by_category else None

        if not cpu_row:
            issues.append("CPU selection is missing or not found in dataset.")
        if not mb_row:
            issues.append("Motherboard selection is missing or not found in dataset.")

        if cpu_row and mb_row:
            cpu_socket = cpu_row.get("socket")
            mb_socket = mb_row.get("socket")
            if cpu_socket and mb_socket and cpu_socket != mb_socket:
                issues.append(f"Socket mismatch: CPU ({cpu_socket}) vs motherboard ({mb_socket}).")

            mb_form = (mb_row.get("form_factor") or "").upper()
            if mb_form and "ITX" in mb_form:
                warnings.append("Mini-ITX motherboards limit expansion and cooling choices.")

        if mem_row and mb_row:
            mem_type = mem_row.get("memory_type") or infer_memory_type(mem_row.get("speed"))
            mb_name = (mb_row.get("name") or "").lower()
            if mem_type == "DDR5" and any(token in mb_name for token in ("b550", "b450", "x570", "a520")):
                issues.append("DDR5 memory selected with a platform that typically expects DDR4.")
            if mem_type == "DDR4" and any(token in mb_name for token in ("b650", "x670", "x870", "z790", "b760")):
                warnings.append("DDR4 memory on a newer platform may be unsupported; verify motherboard specs.")

        estimated_psu = 150
        if cpu_row:
            try:
                estimated_psu += int(float(cpu_row.get("tdp") or 65))
            except ValueError:
                estimated_psu += 65
        if gpu_row:
            chipset = (gpu_row.get("chipset") or "").lower()
            if any(token in chipset for token in ("4090", "4080", "7900 xtx", "7900 xt")):
                estimated_psu += 350
            elif any(token in chipset for token in ("4070", "4060", "3070", "3060", "9060", "9070")):
                estimated_psu += 220
            else:
                estimated_psu += 150

        if psu_row:
            try:
                psu_watts = int(float(psu_row.get("wattage") or 0))
            except ValueError:
                psu_watts = 0
            if psu_watts and psu_watts < estimated_psu:
                issues.append(
                    f"PSU wattage ({psu_watts}W) may be insufficient; estimated need ~{estimated_psu}W."
                )

        if gpu_row and case_row:
            try:
                gpu_len = float(re.sub(r"[^0-9.]", "", str(gpu_row.get("length") or "0")) or 0)
            except ValueError:
                gpu_len = 0
            if gpu_len > 330:
                warnings.append(
                    f"GPU length ({gpu_len}mm) is long; confirm case clearance before finalizing."
                )

        return CompatibilityResult(
            compatible=len(issues) == 0,
            issues=issues,
            warnings=warnings,
            estimated_psu_watts=estimated_psu,
        )

    @staticmethod
    def tool_schema() -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "validate_compatibility",
                "description": (
                    "Validate whether selected PC components are conceptually compatible "
                    "(socket, memory generation, PSU wattage, GPU clearance)."
                ),
                "parameters": CompatibilityCheckRequest.model_json_schema(),
            },
        }
