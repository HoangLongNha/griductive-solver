"""Public hint provider over the current knowledge base (task 4.3).

Privacy boundary (CONTRACTS §0 & §5):
- `get_hint` accepts immutable `PublicState` projections only.
- Hidden labels and unrevealed clues are never inspected or imported.
- Returns at most one currently entailed (row-major first) cell and the
  currently revealed clue IDs supporting the public KB.
"""
from dataclasses import dataclass
from enum import Enum

from griductive.models import CellId, Inference, PublicState, Status

from .deduction import select_forced_verdict
from .entailment import classify_kb
from .knowledge_base import QueryPurpose, SATQuery, build_kb
from .trace import AggregatedSATStats, aggregate_queries


class HintOutcome(str, Enum):
    """Outcome of a public hint request."""

    FORCED = "FORCED"
    NO_FORCED_MOVE = "NO_FORCED_MOVE"
    SOLVED = "SOLVED"
    INCONSISTENT = "INCONSISTENT"


_EMPTY_STATS = AggregatedSATStats(
    sat_calls=0,
    decisions=0,
    propagations=0,
    backtracks=0,
    sat_runtime_s=0.0,
)


@dataclass(frozen=True)
class HintResult:
    """Immutable result returned by `get_hint` for GUI/Controller consumption."""

    outcome: HintOutcome
    cell: CellId | None
    status: Status | None
    revealed_clue_ids: tuple[str, ...]
    message: str
    queries: tuple[SATQuery, ...] = ()
    stats: AggregatedSATStats = _EMPTY_STATS

    def __post_init__(self) -> None:
        if self.outcome == HintOutcome.FORCED:
            if self.cell is None or self.status is None:
                raise ValueError("FORCED hint must include both cell and status")
        else:
            if self.cell is not None or self.status is not None:
                raise ValueError(f"{self.outcome.value} hint must not expose a cell or status")


def _format_forced_message(
    cell: CellId,
    status: Status,
    revealed_clue_ids: tuple[str, ...],
) -> str:
    if revealed_clue_ids:
        clues = ", ".join(revealed_clue_ids)
        return f"Cell {cell} is logically forced to be {status.value} from revealed clues ({clues})."
    return f"Cell {cell} is logically forced to be {status.value} from the current public knowledge."


def get_hint(
    public: PublicState,
    encoder,
    solver,
    *,
    query_log: list[SATQuery] | None = None,
) -> HintResult:
    """Derive a proof-backed hint strictly from `PublicState`.

    All cell classification SAT queries are tagged with `QueryPurpose.HINT`
    (with the initial consistency check tagged `QueryPurpose.BASE_KB`).
    `SolverTimeout` and `SolverCancelled` propagate untouched.
    """
    kb = build_kb(public, encoder)
    if not kb.unresolved_cells:
        return HintResult(
            outcome=HintOutcome.SOLVED,
            cell=None,
            status=None,
            revealed_clue_ids=kb.active_clue_ids,
            message="All cards are already revealed; no hint needed.",
            queries=(),
            stats=_EMPTY_STATS,
        )

    local_log: list[SATQuery] = []
    try:
        inferences = classify_kb(
            kb,
            solver,
            purpose=QueryPurpose.HINT,
            query_log=local_log,
        )
    finally:
        if query_log is not None:
            query_log.extend(local_log)

    queries = tuple(local_log)
    stats = aggregate_queries(queries)

    if any(inf == Inference.INCONSISTENT for inf in inferences.values()):
        return HintResult(
            outcome=HintOutcome.INCONSISTENT,
            cell=None,
            status=None,
            revealed_clue_ids=kb.active_clue_ids,
            message="Public knowledge base is inconsistent; no valid hint is available.",
            queries=queries,
            stats=stats,
        )

    forced = select_forced_verdict(public, inferences)
    if forced is None:
        return HintResult(
            outcome=HintOutcome.NO_FORCED_MOVE,
            cell=None,
            status=None,
            revealed_clue_ids=kb.active_clue_ids,
            message="No cell is currently forced by the revealed clues.",
            queries=queries,
            stats=stats,
        )

    cell, status = forced
    return HintResult(
        outcome=HintOutcome.FORCED,
        cell=cell,
        status=status,
        revealed_clue_ids=kb.active_clue_ids,
        message=_format_forced_message(cell, status, kb.active_clue_ids),
        queries=queries,
        stats=stats,
    )
