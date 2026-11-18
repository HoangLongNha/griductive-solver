"""SAT solver statistics tracking and metrics aggregation (task 3.2).

Metric definitions (CONTRACTS §4 & §7):
- `decisions`: The count of branching choices made by DPLL when selecting an
  unassigned variable to test truth values.
- `propagations`: The count of variables forced to a specific truth value by
  unit clause resolution during unit propagation.
- `backtracks`: The count of branch refutations causing the solver to undo an
  assignment and attempt the opposite polarity or return to a parent decision.
- `runtime_s`: The wall-clock execution time in fractional seconds measured via
  `time.perf_counter()` for a single `solve` query.
"""
from __future__ import annotations

import time
from typing import Iterable, Sequence

from griductive.models import SATStats


class SolverStatsTracker:
    """Mutable tracker collecting metrics during DPLL execution."""

    def __init__(self, start_time: float | None = None) -> None:
        self.decisions = 0
        self.propagations = 0
        self.backtracks = 0
        self.start_time = start_time if start_time is not None else time.perf_counter()

    def record_decision(self) -> None:
        """Record a branching choice on an unassigned variable."""
        self.decisions += 1

    def record_propagation(self, count: int = 1) -> None:
        """Record one or more unit propagation deductions."""
        if count < 0:
            raise ValueError(f"Propagation count cannot be negative: {count}")
        self.propagations += count

    def record_backtrack(self) -> None:
        """Record a backtrack event upon conflict."""
        self.backtracks += 1

    @property
    def elapsed_seconds(self) -> float:
        """Return elapsed wall-clock seconds from tracker initialization."""
        return max(0.0, time.perf_counter() - self.start_time)

    def snapshot(self) -> SATStats:
        """Produce an immutable `SATStats` object representing current metrics."""
        return SATStats(
            decisions=self.decisions,
            propagations=self.propagations,
            backtracks=self.backtracks,
            runtime_s=self.elapsed_seconds,
        )


def zero_stats() -> SATStats:
    """Return an empty SATStats with all counters zeroed."""
    return SATStats(decisions=0, propagations=0, backtracks=0, runtime_s=0.0)


def accumulate_stats(stats_list: Iterable[SATStats]) -> SATStats:
    """Sum decisions, propagations, backtracks, and runtime_s over a sequence of stats."""
    decisions = 0
    propagations = 0
    backtracks = 0
    runtime_s = 0.0

    for s in stats_list:
        if not isinstance(s, SATStats):
            raise TypeError(f"Expected SATStats instance, got {type(s).__name__}")
        decisions += s.decisions
        propagations += s.propagations
        backtracks += s.backtracks
        runtime_s += s.runtime_s

    return SATStats(
        decisions=decisions,
        propagations=propagations,
        backtracks=backtracks,
        runtime_s=runtime_s,
    )


def format_stats_summary(stats: SATStats) -> str:
    """Format SATStats into a human-readable one-line summary."""
    return (
        f"decisions={stats.decisions}, "
        f"propagations={stats.propagations}, "
        f"backtracks={stats.backtracks}, "
        f"runtime={stats.runtime_s * 1000.0:.2f}ms"
    )
