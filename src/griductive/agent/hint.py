"""Public hint provider over the current knowledge base (task 4.3).

Privacy boundary (CONTRACTS §0 & §5):
- `get_hint` accepts immutable `PublicState` projections only.
- Hidden labels and unrevealed clues are never inspected or imported.
- Computes minimal supporting clues (deletion-based MUS) for forced moves,
  prefers the simplest forced cell (fewest supporting clues, ties broken
  row-major), and exposes both Stage-1 (`clue_hint_message`,
  `supporting_clue_cells`) and Stage-2 (`cell`, `status`, `message`) info.
"""
from dataclasses import dataclass
from enum import Enum

from griductive.models import CellId, Inference, PublicCard, PublicState, Status, cell_to_var

from .entailment import classify_kb
from .knowledge_base import (
    QueryPurpose,
    SATQuery,
    _invoke_encoder,
    build_kb,
    run_sat_query,
    validate_public_state,
)
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
    supporting_clue_cells: tuple[CellId, ...] = ()
    clue_hint_message: str = ""

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


def _format_clue_hint_message(
    clue_cells: tuple[CellId, ...],
    clue_ids: tuple[str, ...],
) -> str:
    """Format Stage-1 non-spoiler hint pointing only to supporting clue cells/IDs."""
    if clue_cells and clue_ids:
        pairs = ", ".join(f"{cell} ({cid})" for cell, cid in zip(clue_cells, clue_ids))
        return f"Check the statement(s) at {pairs} to deduce the next forced suspect."
    return "Inspect the confirmed statuses on the board to deduce the next forced suspect."


def _find_minimal_supporting_clues(
    ordered_cards: tuple[PublicCard, ...],
    public: PublicState,
    cell: CellId,
    status: Status,
    encoder,
    solver,
    query_log: list[SATQuery],
) -> tuple[tuple[str, ...], tuple[CellId, ...]]:
    """Deletion-based MUS search over active clues proving `cell == status`."""
    clue_cards = [c for c in ordered_cards if c.revealed and c.clue is not None]
    if not clue_cards:
        return (), ()

    var = cell_to_var(cell, public.size)
    refute_lit = -var if status == Status.CRIMINAL else var
    all_clue_cells = {c.cell for c in clue_cards}
    kept_cells = set(all_clue_cells)

    for card in clue_cards:
        dropped = (all_clue_cells - kept_cells) | {card.cell}
        trial_cards = tuple(
            PublicCard(
                c.cell,
                c.name,
                c.profession,
                c.revealed,
                c.known_status,
                None if c.cell in dropped else c.clue,
            )
            for c in ordered_cards
        )
        trial_state = PublicState(public.puzzle_id, public.size, trial_cards)
        trial_cnf = _invoke_encoder(encoder, trial_state)
        res = run_sat_query(
            solver,
            trial_cnf,
            (refute_lit,),
            purpose=QueryPurpose.HINT,
            target_cell=cell,
            query_log=query_log,
        )
        if not res.is_sat:
            kept_cells.remove(card.cell)

    minimal_cards = [c for c in clue_cards if c.cell in kept_cells]
    return (
        tuple(c.clue.id for c in minimal_cards),  # type: ignore[union-attr]
        tuple(c.cell for c in minimal_cards),
    )


def get_hint(
    public: PublicState,
    encoder,
    solver,
    *,
    query_log: list[SATQuery] | None = None,
) -> HintResult:
    """Derive a proof-backed hint strictly from `PublicState`.

    All cell classification and minimal-clue SAT queries are tagged with
    `QueryPurpose.HINT` (with the initial consistency check tagged
    `QueryPurpose.BASE_KB`). `SolverTimeout` and `SolverCancelled` propagate
    untouched.
    """
    kb = build_kb(public, encoder)
    if not kb.unresolved_cells:
        local_log: list[SATQuery] = []
        try:
            base_result = run_sat_query(
                solver,
                kb.cnf,
                (),
                purpose=QueryPurpose.BASE_KB,
                query_log=local_log,
            )
        finally:
            if query_log is not None:
                query_log.extend(local_log)

        queries = tuple(local_log)
        if not base_result.is_sat:
            msg = "Public knowledge base is inconsistent; no valid hint is available."
            return HintResult(
                outcome=HintOutcome.INCONSISTENT,
                cell=None,
                status=None,
                revealed_clue_ids=kb.active_clue_ids,
                message=msg,
                queries=queries,
                stats=aggregate_queries(queries),
                clue_hint_message=msg,
            )
        msg = "All cards are already revealed; no hint needed."
        return HintResult(
            outcome=HintOutcome.SOLVED,
            cell=None,
            status=None,
            revealed_clue_ids=kb.active_clue_ids,
            message=msg,
            queries=queries,
            stats=aggregate_queries(queries),
            clue_hint_message=msg,
        )

    local_log: list[SATQuery] = []
    try:
        inferences = classify_kb(
            kb,
            solver,
            purpose=QueryPurpose.HINT,
            query_log=local_log,
        )

        if any(inf == Inference.INCONSISTENT for inf in inferences.values()):
            queries = tuple(local_log)
            msg = "Public knowledge base is inconsistent; no valid hint is available."
            return HintResult(
                outcome=HintOutcome.INCONSISTENT,
                cell=None,
                status=None,
                revealed_clue_ids=kb.active_clue_ids,
                message=msg,
                queries=queries,
                stats=aggregate_queries(queries),
                clue_hint_message=msg,
            )

        ordered_cards = validate_public_state(public)
        forced_candidates = [
            (
                card.cell,
                Status.CRIMINAL if inferences[card.cell] == Inference.CRIMINAL else Status.INNOCENT,
            )
            for card in ordered_cards
            if not card.revealed
            and inferences.get(card.cell) in (Inference.CRIMINAL, Inference.INNOCENT)
        ]

        if not forced_candidates:
            queries = tuple(local_log)
            msg = "No cell is currently forced by the revealed clues."
            return HintResult(
                outcome=HintOutcome.NO_FORCED_MOVE,
                cell=None,
                status=None,
                revealed_clue_ids=kb.active_clue_ids,
                message=msg,
                queries=queries,
                stats=aggregate_queries(queries),
                clue_hint_message=msg,
            )

        best_cell, best_status = forced_candidates[0]
        best_clue_ids: tuple[str, ...] = ()
        best_clue_cells: tuple[CellId, ...] = ()
        best_len = float("inf")

        for cand_cell, cand_status in forced_candidates:
            clue_ids, clue_cells = _find_minimal_supporting_clues(
                ordered_cards,
                public,
                cand_cell,
                cand_status,
                encoder,
                solver,
                local_log,
            )
            if len(clue_ids) < best_len:
                best_len = len(clue_ids)
                best_cell = cand_cell
                best_status = cand_status
                best_clue_ids = clue_ids
                best_clue_cells = clue_cells
                if best_len <= 1:
                    break

        queries = tuple(local_log)
        stats = aggregate_queries(queries)
        return HintResult(
            outcome=HintOutcome.FORCED,
            cell=best_cell,
            status=best_status,
            revealed_clue_ids=best_clue_ids,
            message=_format_forced_message(best_cell, best_status, best_clue_ids),
            queries=queries,
            stats=stats,
            supporting_clue_cells=best_clue_cells,
            clue_hint_message=_format_clue_hint_message(best_clue_cells, best_clue_ids),
        )
    finally:
        if query_log is not None:
            query_log.extend(local_log)
