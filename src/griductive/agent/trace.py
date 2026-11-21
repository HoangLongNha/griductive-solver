"""Deduction trace and aggregated SAT metric models (task 4.2).

Per CONTRACTS §5 & §7:
- Every step records active clue IDs, CNF counts, actual SAT assumptions and
  results, the forced verdict, the newly revealed clue ID, and step metrics.
- Aggregate counters always equal the exact sum of per-call `SATQuery` records.
- SAT runtime (`totals.sat_runtime_s`) is tracked separately from end-to-end
  wall-clock runtime (`total_runtime_s`).
"""
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from griductive.models import CellId, PublicState, Status, VerdictStatus

from .knowledge_base import CNFMetrics, SATQuery


class TraceStatus(str, Enum):
    """Terminal status of a deduction run."""

    SOLVED = "SOLVED"
    STUCK = "STUCK"
    INCONSISTENT = "INCONSISTENT"


@dataclass(frozen=True)
class AggregatedSATStats:
    """Sum of solver counters across a collection of `SATQuery` records."""

    sat_calls: int
    decisions: int
    propagations: int
    backtracks: int
    sat_runtime_s: float


def aggregate_queries(queries: Iterable[SATQuery]) -> AggregatedSATStats:
    """Compute exact totals by summing per-call `SATQuery` records."""
    items = tuple(queries)
    return AggregatedSATStats(
        sat_calls=len(items),
        decisions=sum(q.stats.decisions for q in items),
        propagations=sum(q.stats.propagations for q in items),
        backtracks=sum(q.stats.backtracks for q in items),
        sat_runtime_s=sum(q.stats.runtime_s for q in items),
    )


@dataclass(frozen=True)
class DeductionStep:
    """One accepted proof-backed deduction step in `auto_solve`."""

    step_index: int
    active_clue_ids: tuple[str, ...]
    cnf_metrics: CNFMetrics
    queries: tuple[SATQuery, ...]
    cell: CellId
    verdict: Status
    outcome: VerdictStatus
    newly_revealed_cell: CellId | None
    newly_revealed_clue_id: str | None
    stats: AggregatedSATStats
    cumulative_stats: AggregatedSATStats
    step_runtime_s: float

    @property
    def step_number(self) -> int:
        """1-based step number alias (Notion v0.2 `DeductionStep` schema)."""
        return self.step_index


@dataclass(frozen=True)
class DeductionTrace:
    """Complete immutable audit log of a no-guess deduction run."""

    puzzle_id: str
    status: TraceStatus
    steps: tuple[DeductionStep, ...]
    terminal_queries: tuple[SATQuery, ...]
    all_queries: tuple[SATQuery, ...]
    totals: AggregatedSATStats
    total_runtime_s: float
    final_state: PublicState
    message: str = ""

    @property
    def terminal(self) -> TraceStatus:
        """Terminal status alias (Notion v0.2 `DeductionTrace` schema)."""
        return self.status

    @property
    def deduction_steps(self) -> int:
        return len(self.steps)

    @property
    def total_sat_calls(self) -> int:
        return self.totals.sat_calls


def build_trace(
    *,
    puzzle_id: str,
    status: TraceStatus,
    steps: Iterable[DeductionStep],
    terminal_queries: Iterable[SATQuery],
    total_runtime_s: float,
    final_state: PublicState,
    message: str = "",
) -> DeductionTrace:
    """Assemble a `DeductionTrace` guaranteeing `totals == aggregate_queries(all_queries)`."""
    step_tuple = tuple(steps)
    terminal_tuple = tuple(terminal_queries)
    all_queries = tuple(q for step in step_tuple for q in step.queries) + terminal_tuple
    return DeductionTrace(
        puzzle_id=puzzle_id,
        status=status,
        steps=step_tuple,
        terminal_queries=terminal_tuple,
        all_queries=all_queries,
        totals=aggregate_queries(all_queries),
        total_runtime_s=total_runtime_s,
        final_state=final_state,
        message=message,
    )
