"""Public knowledge base construction and SAT query wrapper (task 4.1).

Privacy boundary: the agent accepts immutable `PublicState` projections only.
Hidden puzzle truths and face-down clues are never imported, inspected, or read.
"""
from dataclasses import dataclass
from enum import Enum

from griductive.models import (
    CNF,
    CellId,
    PublicCard,
    PublicState,
    SATResult,
    SATStats,
    cell_to_var,
    var_to_cell,
)


class QueryPurpose(str, Enum):
    """Purpose label attached to each SAT solver invocation (CONTRACTS §7)."""

    BASE_KB = "BASE_KB"
    CLASSIFY = "CLASSIFY"
    VERDICT_RECHECK = "VERDICT_RECHECK"
    HINT = "HINT"
    UNIQUENESS = "UNIQUENESS"
    VALIDATION = "VALIDATION"


@dataclass(frozen=True)
class CNFMetrics:
    """Variable and clause counts of an encoded KB snapshot."""

    primary_count: int
    aux_count: int
    clause_count: int


@dataclass(frozen=True)
class SATQuery:
    """Audit record for a single completed SAT query."""

    purpose: QueryPurpose
    target_cell: CellId | None
    assumptions: tuple[int, ...]
    is_sat: bool
    stats: SATStats


@dataclass(frozen=True)
class KnowledgeBase:
    """Encoded public knowledge base at one point in gameplay."""

    puzzle_id: str
    size: int
    cnf: CNF
    active_clue_ids: tuple[str, ...]
    revealed_cells: frozenset[CellId]
    unresolved_cells: tuple[CellId, ...]

    @property
    def metrics(self) -> CNFMetrics:
        return CNFMetrics(
            primary_count=self.cnf.primary_count,
            aux_count=self.cnf.variable_count - self.cnf.primary_count,
            clause_count=len(self.cnf.clauses),
        )


def validate_public_state(public: PublicState) -> tuple[PublicCard, ...]:
    """Validate privacy and structural invariants, returning cards in row-major order."""
    if not isinstance(public, PublicState):
        raise TypeError("Agent accepts PublicState projections only")
    if type(public.size) is not int or not 1 <= public.size <= 26:
        raise ValueError("Board size must be an integer in 1..26")

    expected_count = public.size * public.size
    if len(public.cards) != expected_count:
        raise ValueError(f"Expected {expected_count} cards for {public.size}x{public.size} board")

    by_var: dict[int, PublicCard] = {}
    for card in public.cards:
        if not isinstance(card, PublicCard):
            raise TypeError("PublicState.cards must contain PublicCard instances only")
        if not card.revealed and (card.known_status is not None or card.clue is not None):
            raise ValueError(f"Face-down card {card.cell} must not expose status or clue")
        var = cell_to_var(card.cell, public.size)
        if var in by_var:
            raise ValueError(f"Duplicate cell in PublicState: {card.cell}")
        by_var[var] = card

    expected_vars = range(1, expected_count + 1)
    missing = [var_to_cell(v, public.size) for v in expected_vars if v not in by_var]
    if missing:
        raise ValueError(f"Missing cells in PublicState: {missing}")

    return tuple(by_var[v] for v in expected_vars)


def _invoke_encoder(encoder, public: PublicState) -> CNF:
    """Invoke either a plain function `encode_kb(public)` or an object with `.encode_kb(public)`."""
    if callable(encoder):
        cnf = encoder(public)
    elif hasattr(encoder, "encode_kb") and callable(encoder.encode_kb):
        cnf = encoder.encode_kb(public)
    else:
        raise TypeError("encoder must be callable or expose encode_kb(public)")
    if not isinstance(cnf, CNF):
        raise TypeError("encoder must return a CNF instance")
    return cnf


def _invoke_solver(solver, cnf: CNF, assumptions: tuple[int, ...]) -> SATResult:
    """Invoke either a plain function `solve(cnf, assumptions=...)` or an object with `.solve(...)`."""
    if callable(solver):
        result = solver(cnf, assumptions=assumptions)
    elif hasattr(solver, "solve") and callable(solver.solve):
        result = solver.solve(cnf, assumptions=assumptions)
    else:
        raise TypeError("solver must be callable or expose solve(cnf, assumptions=())")
    if not isinstance(result, SATResult):
        raise TypeError("solver must return a SATResult instance")
    return result


def build_kb(public: PublicState, encoder) -> KnowledgeBase:
    """Build a public `KnowledgeBase` from a `PublicState` via the injected CNF encoder."""
    ordered_cards = validate_public_state(public)
    cnf = _invoke_encoder(encoder, public)

    expected_primary = public.size * public.size
    if cnf.primary_count != expected_primary:
        raise ValueError(
            f"CNF primary_count ({cnf.primary_count}) does not match board size ({expected_primary})"
        )
    if cnf.variable_count < cnf.primary_count:
        raise ValueError("CNF variable_count cannot be smaller than primary_count")

    active_clue_ids = tuple(
        card.clue.id for card in ordered_cards if card.revealed and card.clue is not None
    )
    revealed_cells = frozenset(card.cell for card in ordered_cards if card.revealed)
    unresolved_cells = tuple(card.cell for card in ordered_cards if not card.revealed)

    return KnowledgeBase(
        puzzle_id=public.puzzle_id,
        size=public.size,
        cnf=cnf,
        active_clue_ids=active_clue_ids,
        revealed_cells=revealed_cells,
        unresolved_cells=unresolved_cells,
    )


def run_sat_query(
    solver,
    cnf: CNF,
    assumptions: tuple[int, ...] = (),
    *,
    purpose: QueryPurpose = QueryPurpose.CLASSIFY,
    target_cell: CellId | None = None,
    query_log: list[SATQuery] | None = None,
) -> SATResult:
    """Run one SAT query with temporary assumptions and optionally append an audit record.

    `SolverTimeout` and `SolverCancelled` propagate untouched and are never treated as UNSAT.
    """
    normalized = tuple(assumptions)
    for lit in normalized:
        if type(lit) is not int or not 1 <= abs(lit) <= cnf.variable_count:
            raise ValueError(f"Invalid assumption literal: {lit}")

    result = _invoke_solver(solver, cnf, normalized)
    if query_log is not None:
        query_log.append(
            SATQuery(
                purpose=purpose,
                target_cell=target_cell,
                assumptions=normalized,
                is_sat=result.is_sat,
                stats=result.stats,
            )
        )
    return result
