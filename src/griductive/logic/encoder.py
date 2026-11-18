"""Automatic CNF encoding of clues and the public knowledge base (task 2.2).

Primary variable of cell X is `cell_to_var(X, N)` (row-major, 1..N*N, True =
Criminal). Auxiliary variables start at N*N+1 and are allocated in a fixed
order: known verdicts first, then revealed clues in row-major card order.
No formula is written per puzzle; every clue goes through `encode_clue`.
"""
from collections.abc import Iterable

from griductive.models import CNF, CellId, Clause, Clue, PublicState, cell_to_var
from .cardinality import AuxPool, at_least, at_most, exactly
from .regions import check_size, parse_literal, parse_status
from .semantics import check_clue, parse_counting, parse_pair


def literal(cell: CellId, criminal: bool, size: int) -> int:
    var = cell_to_var(cell, size)
    return var if criminal else -var


def encode_clue(clue: Clue, size: int, pool: AuxPool) -> list[Clause]:
    """CNF for one validated clue; raises `ClueValidationError` if invalid."""
    check_clue(clue, size)

    def var(cell):
        return cell_to_var(cell, size)

    if clue.kind == 'FACT':
        cell, criminal = parse_literal(clue.data, size)
        return [(literal(cell, criminal, size),)]
    if clue.kind == 'SAME':
        a, b = map(var, parse_pair(clue, size))
        return [(-a, b), (a, -b)]
    if clue.kind == 'DIFFERENT':
        a, b = map(var, parse_pair(clue, size))
        return [(a, b), (-a, -b)]
    cells, k = parse_counting(clue, size)
    encode = {'EXACTLY': exactly, 'AT_LEAST': at_least, 'AT_MOST': at_most}[clue.kind]
    return encode(tuple(map(var, cells)), k, pool)


def _build(size: int, units: Iterable[Clause], clues: Iterable[Clue]) -> CNF:
    check_size(size)
    pool = AuxPool(size * size)
    clauses = list(units)
    for clue in clues:
        clauses += encode_clue(clue, size, pool)
    return CNF(tuple(clauses), pool.primary_count, pool.top)


def encode_kb(public: PublicState) -> CNF:
    """KB_t = CNF(revealed clues) AND unit clauses for proved verdicts.

    Reads only face-up cards of the public snapshot; hidden data is never seen.
    """
    revealed = [card for card in public.cards if card.revealed]
    units = [(literal(card.cell, parse_status(card.known_status), public.size),)
             for card in revealed if card.known_status is not None]
    return _build(public.size, units, [card.clue for card in revealed if card.clue is not None])


def encode_full_clues(puzzle) -> CNF:
    """All clues of a puzzle, no verdict units. Validation/uniqueness only; NEVER from the agent."""
    return _build(puzzle.size, (), [card.clue for card in puzzle.cards])


def active_clue_ids(public: PublicState) -> tuple[str, ...]:
    """IDs of the clues that make up KB_t, in encoding order."""
    return tuple(card.clue.id for card in public.cards if card.revealed and card.clue is not None)


def cnf_counts(cnf: CNF) -> dict[str, int]:
    """Sizes to report per puzzle/step: primary, auxiliary and clause counts."""
    return {'primary_count': cnf.primary_count,
            'aux_count': cnf.variable_count - cnf.primary_count,
            'clause_count': len(cnf.clauses)}
