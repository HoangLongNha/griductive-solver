"""Offline full-clue uniqueness checker (task 4.3, validation scope only).

Architecture boundary (CONTRACTS §3 & §5):
- Lives in `griductive.validation`, strictly separate from the public Agent.
- Evaluates the COMPLETE clue set (via `encode_full_clues`, with NO verdict
  unit clauses and NO hidden-status assumptions) to verify whether exactly one
  primary assignment satisfies all clues.
- Blocking clauses range over primary variables `1..primary_count` ONLY so that
  multiple auxiliary-variable completions of the same primary model are never
  misclassified as distinct puzzle solutions.
- Full-clue uniqueness is independent of no-guess playability from initial
  public knowledge.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from griductive.agent.knowledge_base import QueryPurpose, SATQuery, run_sat_query
from griductive.agent.trace import AggregatedSATStats, aggregate_queries
from griductive.models import CNF, Clause, PublicState


class UniquenessStatus(str, Enum):
    """Classification of the primary solution count of a full clue set."""

    UNIQUE = "UNIQUE"
    MULTIPLE = "MULTIPLE"
    UNSAT = "UNSAT"


@dataclass(frozen=True)
class UniquenessResult:
    """Detailed audit result of a full-clue uniqueness check."""

    is_unique: bool
    status: UniquenessStatus
    first_model: Mapping[int, bool] | None
    second_model: Mapping[int, bool] | None
    blocking_clause: Clause | None
    queries: tuple[SATQuery, ...]
    stats: AggregatedSATStats


def _extract_primary_model(
    assignment: Mapping[int, bool] | None,
    primary_count: int,
) -> Mapping[int, bool]:
    """Validate and project a SAT assignment onto primary variables `1..primary_count`."""
    if assignment is None:
        raise ValueError("SAT solver returned SAT without an assignment")
    primary: dict[int, bool] = {}
    for var in range(1, primary_count + 1):
        if var not in assignment:
            raise ValueError(f"SAT assignment missing primary variable {var}")
        value = assignment[var]
        if type(value) is not bool:
            raise TypeError(f"SAT assignment for variable {var} must be bool")
        primary[var] = value
    return MappingProxyType(primary)


def build_primary_blocking_clause(
    assignment: Mapping[int, bool],
    primary_count: int,
) -> Clause:
    """Build a blocking clause over primary variables `1..primary_count` only.

    For each primary variable `v`:
    - `True`  (Criminal) -> `-v`
    - `False` (Innocent) -> `+v`

    Auxiliary variables (`v > primary_count`) are strictly excluded.
    """
    if type(primary_count) is not int or primary_count < 1:
        raise ValueError("primary_count must be a positive integer")
    primary = _extract_primary_model(assignment, primary_count)
    return tuple(-var if primary[var] else var for var in range(1, primary_count + 1))


def _validate_cnf(cnf: CNF) -> None:
    if not isinstance(cnf, CNF):
        raise TypeError("cnf must be a CNF instance")
    if type(cnf.primary_count) is not int or cnf.primary_count < 1:
        raise ValueError("CNF primary_count must be a positive integer")
    if type(cnf.variable_count) is not int or cnf.variable_count < cnf.primary_count:
        raise ValueError("CNF variable_count cannot be smaller than primary_count")


def _invoke_full_encoder(encoder, puzzle) -> CNF:
    """Invoke a callable `encode_full_clues(puzzle)` or an object exposing `.encode_full_clues`."""
    if isinstance(puzzle, PublicState):
        raise TypeError("Full-clue uniqueness check requires a complete Puzzle, not PublicState")
    if callable(encoder):
        cnf = encoder(puzzle)
    elif hasattr(encoder, "encode_full_clues") and callable(encoder.encode_full_clues):
        cnf = encoder.encode_full_clues(puzzle)
    else:
        raise TypeError("encoder must be callable or expose encode_full_clues(puzzle)")
    _validate_cnf(cnf)
    if hasattr(puzzle, "size") and type(puzzle.size) is int:
        expected_primary = puzzle.size * puzzle.size
        if cnf.primary_count != expected_primary:
            raise ValueError(
                f"CNF primary_count ({cnf.primary_count}) does not match board size ({expected_primary})"
            )
    return cnf


def analyze_unique_cnf(
    cnf: CNF,
    solver,
    *,
    query_log: list[SATQuery] | None = None,
) -> UniquenessResult:
    """Check whether `cnf` has a unique primary assignment (at most 2 SAT calls).

    `SolverTimeout` and `SolverCancelled` propagate untouched and are never
    interpreted as UNSAT or UNIQUE.
    """
    _validate_cnf(cnf)
    local_log: list[SATQuery] = []
    try:
        res1 = run_sat_query(
            solver,
            cnf,
            (),
            purpose=QueryPurpose.UNIQUENESS,
            target_cell=None,
            query_log=local_log,
        )
        if not res1.is_sat:
            queries = tuple(local_log)
            return UniquenessResult(
                is_unique=False,
                status=UniquenessStatus.UNSAT,
                first_model=None,
                second_model=None,
                blocking_clause=None,
                queries=queries,
                stats=aggregate_queries(queries),
            )

        first_primary = _extract_primary_model(res1.assignment, cnf.primary_count)
        blocking_clause = build_primary_blocking_clause(first_primary, cnf.primary_count)
        blocked_cnf = CNF(
            clauses=cnf.clauses + (blocking_clause,),
            primary_count=cnf.primary_count,
            variable_count=cnf.variable_count,
        )

        res2 = run_sat_query(
            solver,
            blocked_cnf,
            (),
            purpose=QueryPurpose.UNIQUENESS,
            target_cell=None,
            query_log=local_log,
        )
    finally:
        if query_log is not None:
            query_log.extend(local_log)

    queries = tuple(local_log)
    stats = aggregate_queries(queries)

    if not res2.is_sat:
        return UniquenessResult(
            is_unique=True,
            status=UniquenessStatus.UNIQUE,
            first_model=first_primary,
            second_model=None,
            blocking_clause=blocking_clause,
            queries=queries,
            stats=stats,
        )

    second_primary = _extract_primary_model(res2.assignment, cnf.primary_count)
    if second_primary == first_primary:
        raise ValueError("Solver returned a second model violating the primary blocking clause")

    return UniquenessResult(
        is_unique=False,
        status=UniquenessStatus.MULTIPLE,
        first_model=first_primary,
        second_model=second_primary,
        blocking_clause=blocking_clause,
        queries=queries,
        stats=stats,
    )


def check_unique_cnf(
    cnf: CNF,
    solver,
    *,
    query_log: list[SATQuery] | None = None,
) -> bool:
    """Return `True` iff `cnf` has exactly one satisfying primary assignment."""
    return analyze_unique_cnf(cnf, solver, query_log=query_log).is_unique


def analyze_unique_complete(
    puzzle,
    encoder,
    solver,
    *,
    query_log: list[SATQuery] | None = None,
) -> UniquenessResult:
    """Encode all clues of `puzzle` (validation-only) and analyze primary uniqueness."""
    cnf = _invoke_full_encoder(encoder, puzzle)
    return analyze_unique_cnf(cnf, solver, query_log=query_log)


def check_unique_complete(
    puzzle,
    encoder,
    solver,
    *,
    query_log: list[SATQuery] | None = None,
) -> bool:
    """Return `True` iff the complete clue set of `puzzle` admits a unique primary solution."""
    return analyze_unique_complete(puzzle, encoder, solver, query_log=query_log).is_unique
