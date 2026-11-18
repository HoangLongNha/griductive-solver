"""Team extensions PARITY and COMPOUND: direct evaluator and CNF (task 2.3).

- PARITY {parity: ODD|EVEN, region}: the number of criminals in the region is odd/even.
- COMPOUND {premises: [{cell, status}...], conclusion: {cell, status}}:
  (p1 AND ... AND pm) -> q, i.e. the single clause (-p1 OR ... OR -pm OR q).
"""
from collections.abc import Mapping
from itertools import product

from griductive.models import CellId, Clause, Clue
from .cardinality import DIRECT_CLAUSE_LIMIT, AuxPool
from .regions import ClueValidationError, field, parse_literal, resolve_region

EXTENSION_KINDS = ('PARITY', 'COMPOUND')


def parse_parity(clue: Clue, size: int) -> tuple[tuple[CellId, ...], bool]:
    """(region cells, odd)."""
    cells = resolve_region(field(clue.data, 'region'), size)
    parity = field(clue.data, 'parity')
    if parity not in ('ODD', 'EVEN'):
        raise ClueValidationError(f'Parity must be ODD or EVEN, got {parity!r}')
    return cells, parity == 'ODD'


def parse_compound(clue: Clue, size: int):
    """(premises, conclusion) as (cell, is_criminal) literals."""
    premises = field(clue.data, 'premises')
    if not isinstance(premises, (list, tuple)) or not premises:
        raise ClueValidationError('COMPOUND needs a non-empty list of premises')
    return (tuple(parse_literal(item, size) for item in premises),
            parse_literal(field(clue.data, 'conclusion'), size))


def referenced_cells(clue: Clue, size: int) -> tuple[CellId, ...]:
    if clue.kind == 'PARITY':
        return parse_parity(clue, size)[0]
    if clue.kind == 'COMPOUND':
        premises, conclusion = parse_compound(clue, size)
        return tuple(dict.fromkeys(cell for cell, _ in (*premises, conclusion)))
    raise ClueValidationError(f'Not an extension clue: {clue.kind!r}')


def evaluate(clue: Clue, full_assignment: Mapping[CellId, bool], size: int) -> bool:
    """Direct semantics; never calls the encoder or a solver."""
    if clue.kind == 'PARITY':
        cells, odd = parse_parity(clue, size)
        return sum(full_assignment[cell] for cell in cells) % 2 == odd
    if clue.kind != 'COMPOUND':
        raise ClueValidationError(f'Not an extension clue: {clue.kind!r}')
    premises, (cell, criminal) = parse_compound(clue, size)
    if all(full_assignment[c] == value for c, value in premises):
        return full_assignment[cell] == criminal
    return True


def encode_parity(lits: tuple[int, ...], odd: bool, pool: AuxPool,
                  direct_limit: int = DIRECT_CLAUSE_LIMIT) -> list[Clause]:
    """Direct truth-table exclusion when 2^(n-1) clauses fit, otherwise a Tseitin XOR chain."""
    n = len(lits)
    if 2 ** (n - 1) <= direct_limit:
        # Forbid every assignment of the region with the wrong parity.
        return [tuple(-lit if bit else lit for lit, bit in zip(lits, bits))
                for bits in product((False, True), repeat=n) if sum(bits) % 2 != odd]
    clauses, acc = [], lits[0]
    for lit in lits[1:]:
        t = pool.new()  # t <-> acc XOR lit
        clauses += [(-t, acc, lit), (-t, -acc, -lit), (t, -acc, lit), (t, acc, -lit)]
        acc = t
    clauses.append((acc,) if odd else (-acc,))
    return clauses


def encode_compound(premises: tuple[int, ...], conclusion: int) -> list[Clause]:
    """(p1 AND ... AND pm) -> q as one clause; dropped when tautological."""
    clause = tuple(dict.fromkeys((*(-lit for lit in premises), conclusion)))
    if any(-lit in clause for lit in clause):
        return []
    return [clause]
