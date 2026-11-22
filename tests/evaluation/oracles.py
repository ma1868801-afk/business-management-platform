"""Runs the reference oracle queries of `tests/evaluation/oracles.yaml`
(06_evaluation_plan.md section 6) against the live database and exposes the resulting
values to the grader for the numeric-tolerance comparison of section 4.7.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import yaml

ORACLES_PATH = Path(__file__).resolve().parent / "oracles.yaml"


@dataclass
class OracleResult:
    scenario_id: str
    shape: str
    rows: list[dict]  # always a list; single_row has exactly one entry

    def as_single_row(self) -> dict:
        return self.rows[0] if self.rows else {}

    def numbers(self) -> set[float]:
        """Every numeric value across every row, flattened -- what the grader's numeric
        tolerance check (section 4.7) compares an answer's figures against."""
        out: set[float] = set()
        for row in self.rows:
            for v in row.values():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    out.add(float(v))
        return out


class OracleStore:
    def __init__(self, path: Path = ORACLES_PATH):
        self._entries: dict[str, dict] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def has(self, scenario_id: str) -> bool:
        return scenario_id in self._entries

    def run(self, scenario_id: str, postgres_executor: Callable[[str, int], dict]) -> Optional[OracleResult]:
        entry = self._entries.get(scenario_id)
        if entry is None:
            return None
        out = postgres_executor(entry["sql"], 500)
        if "error" in out:
            raise RuntimeError(f"oracle query for {scenario_id} failed: {out['error']}")
        rows = [dict(zip(out["columns"], row)) for row in out["rows"]]
        for row in rows:
            for k, v in list(row.items()):
                if isinstance(v, str):
                    try:
                        row[k] = float(v)
                    except ValueError:
                        pass
        return OracleResult(scenario_id=scenario_id, shape=entry.get("shape", "single_row"), rows=rows)
