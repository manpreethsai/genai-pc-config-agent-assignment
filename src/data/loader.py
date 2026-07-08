"""Load and index component CSV datasets."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from src.config import settings

CATEGORY_FILES = {
    "cpu": "cpu.csv",
    "motherboard": "motherboard.csv",
    "memory": "memory.csv",
    "video_card": "video-card.csv",
    "power_supply": "power-supply.csv",
    "case": "case.csv",
    "internal_hard_drive": "internal-hard-drive.csv",
    "cpu_cooler": "cpu-cooler.csv",
}

ARCHITECTURE_TO_SOCKET = {
    "zen 5": "AM5",
    "zen 4": "AM5",
    "zen 3": "AM4",
    "zen 2": "AM4",
    "zen+": "AM4",
    "zen": "AM4",
    "arrow lake": "LGA1851",
    "raptor lake refresh": "LGA1700",
    "raptor lake": "LGA1700",
    "alder lake": "LGA1700",
    "meteor lake": "LGA1851",
    "comet lake": "LGA1200",
    "coffee lake refresh": "LGA1151",
    "coffee lake": "LGA1151",
    "kaby lake": "LGA1151",
    "skylake": "LGA1151",
    "broadwell": "LGA1151",
    "haswell refresh": "LGA1150",
    "haswell": "LGA1150",
    "ivy bridge": "LGA1155",
    "sandy bridge": "LGA1155",
}


def _parse_price(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def infer_cpu_socket(cpu_row: dict[str, str]) -> str | None:
    arch = (cpu_row.get("microarchitecture") or "").strip().lower()
    if arch in ARCHITECTURE_TO_SOCKET:
        return ARCHITECTURE_TO_SOCKET[arch]

    name = (cpu_row.get("name") or "").lower()
    if "ryzen" in name:
        if any(token in name for token in ("9800", "9700", "9600", "9500", "8700", "8600", "8500", "8400", "7800", "7700", "7600", "7500")):
            return "AM5"
        return "AM4"
    if "core ultra" in name:
        return "LGA1851"
    if any(token in name for token in ("14900", "14700", "14600", "14500", "14400", "13900", "13700", "13600", "13500", "13400")):
        return "LGA1700"
    if any(token in name for token in ("12900", "12700", "12600", "12500", "12400")):
        return "LGA1700"
    if any(token in name for token in ("11900", "11700", "11600", "11400", "10900", "10700", "10600", "10400")):
        return "LGA1200"
    return None


def infer_memory_type(speed: str | None) -> str:
    if not speed:
        return "unknown"
    cleaned = speed.strip()
    if "," in cleaned:
        generation_prefix = cleaned.split(",", 1)[0].strip()
        if generation_prefix == "5":
            return "DDR5"
        if generation_prefix == "4":
            return "DDR4"
    digits = re.sub(r"[^0-9]", "", cleaned)
    if not digits:
        return "unknown"
    try:
        mhz = int(digits)
    except ValueError:
        return "unknown"
    return "DDR5" if mhz >= 4800 else "DDR4"


class ComponentRepository:
    """In-memory repository over the provided CSV files."""

    def __init__(self, dataset_path: Path | None = None) -> None:
        self.dataset_path = dataset_path or settings.dataset_path
        self._data: dict[str, list[dict[str, Any]]] = {}
        self._load_all()

    def _load_all(self) -> None:
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset path not found: {self.dataset_path}")

        for category, filename in CATEGORY_FILES.items():
            file_path = self.dataset_path / filename
            if not file_path.exists():
                raise FileNotFoundError(f"Missing dataset file: {file_path}")

            rows: list[dict[str, Any]] = []
            with file_path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    normalized = {key: (value or "").strip() for key, value in row.items()}
                    normalized["price"] = _parse_price(normalized.get("price"))
                    normalized["category"] = category
                    if category == "cpu":
                        normalized["socket"] = infer_cpu_socket(normalized)
                    if category == "memory":
                        normalized["memory_type"] = infer_memory_type(normalized.get("speed"))
                    rows.append(normalized)
            self._data[category] = rows

    def list_categories(self) -> list[str]:
        return list(self._data.keys())

    def get_category_rows(self, category: str) -> list[dict[str, Any]]:
        return self._data.get(category, [])

    def find_by_name(self, category: str, name: str) -> dict[str, Any] | None:
        target = name.strip().lower()
        for row in self.get_category_rows(category):
            if row.get("name", "").strip().lower() == target:
                return row
        return None
