"""Component query tool used by the agent."""

from __future__ import annotations

from typing import Any

from src.data.loader import ComponentRepository
from src.models.schemas import ComponentCategory, ComponentQueryParams


class ComponentQueryTool:
    """Filter components from the local dataset."""

    def __init__(self, repository: ComponentRepository) -> None:
        self.repository = repository

    def query(self, params: ComponentQueryParams) -> dict[str, Any]:
        category = params.category.value
        rows = self.repository.get_category_rows(category)
        filtered: list[dict[str, Any]] = []

        for row in rows:
            price = row.get("price")
            if price is None:
                continue
            if params.min_price is not None and price < params.min_price:
                continue
            if params.max_price is not None and price > params.max_price:
                continue
            if params.socket and row.get("socket") != params.socket:
                continue
            if params.form_factor and row.get("form_factor") != params.form_factor:
                if params.form_factor not in (row.get("type") or ""):
                    continue
            if params.brand_preference:
                brand = params.brand_preference.lower()
                if brand not in row.get("name", "").lower():
                    continue
            if params.keyword:
                keyword = params.keyword.lower()
                haystack = " ".join(str(v) for v in row.values()).lower()
                if keyword not in haystack:
                    continue
            filtered.append(row)

        filtered.sort(key=lambda item: item.get("price") or float("inf"))
        limited = filtered[: params.limit]

        return {
            "category": category,
            "count": len(limited),
            "total_matches": len(filtered),
            "results": [
                {
                    "name": row.get("name"),
                    "price": row.get("price"),
                    "socket": row.get("socket"),
                    "form_factor": row.get("form_factor"),
                    "memory_type": row.get("memory_type"),
                    "wattage": row.get("wattage"),
                    "tdp": row.get("tdp"),
                    "chipset": row.get("chipset"),
                    "capacity": row.get("capacity"),
                    "modules": row.get("modules"),
                    "length": row.get("length"),
                }
                for row in limited
            ],
        }

    @staticmethod
    def tool_schema() -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "query_components",
                "description": (
                    "Search the PC components dataset by category and optional filters "
                    "(price range, socket, form factor, brand, keyword)."
                ),
                "parameters": ComponentQueryParams.model_json_schema(),
            },
        }
