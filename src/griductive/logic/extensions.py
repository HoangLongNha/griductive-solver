"""Team extensions PARITY, COMPOUND, and CONNECTED: direct evaluator and CNF (task 2.3).

- PARITY {parity: ODD|EVEN, region, status?: CRIMINAL|INNOCENT}: count of status in region is odd/even.
- COMPOUND {premises: [{cell, status}...], conclusion: {cell, status}}:
  (p1 AND ... AND pm) -> q, i.e. the single clause (-p1 OR ... OR -pm OR q).
- CONNECTED {region, status?: CRIMINAL|INNOCENT}: all cells with target status in region
  form a single orthogonally connected (4-directional up/down/left/right) component.
"""
from collections import deque
from collections.abc import Mapping
from itertools import product

from griductive.models import CellId, Clause, Clue
from .cardinality import DIRECT_CLAUSE_LIMIT, AuxPool
from .regions import ClueValidationError, field, parse_literal, parse_status, resolve_region

EXTENSION_KINDS = ('PARITY', 'COMPOUND', 'CONNECTED')


def parse_target_status(clue: Clue) -> bool:
    if 'status' not in clue.data:
        return True
    return parse_status(clue.data['status'])


def parse_parity(clue: Clue, size: int) -> tuple[tuple[CellId, ...], bool]:
    """(region cells, odd)."""
    cells = resolve_region(field(clue.data, 'region'), size)
    parse_target_status(clue)
    parity = field(clue.data, 'parity')
    if parity not in ('ODD', 'EVEN'):
        raise ClueValidationError(f'Parity must be ODD or EVEN, got {parity!r}')
    return cells, parity == 'ODD'


def parse_connected(clue: Clue, size: int) -> tuple[tuple[CellId, ...], bool]:
    """(region cells, target_is_criminal)."""
    cells = resolve_region(field(clue.data, 'region'), size)
    return cells, parse_target_status(clue)


def _is_orthogonally_connected(active_cells: set[CellId]) -> bool:
    """True if active_cells has <=1 cell or forms one 4-neighbor (edge-adjacent) component."""
    if len(active_cells) <= 1:
        return True
    coords = {cell: (ord(cell[0]) - 65, int(cell[1:]) - 1) for cell in active_cells}
    start = next(iter(active_cells))
    visited = {start}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        cx, cy = coords[cur]
        for other, (ox, oy) in coords.items():
            if other not in visited and abs(cx - ox) + abs(cy - oy) == 1:
                visited.add(other)
                queue.append(other)
    return len(visited) == len(active_cells)


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
    if clue.kind == 'CONNECTED':
        return parse_connected(clue, size)[0]
    if clue.kind == 'COMPOUND':
        premises, conclusion = parse_compound(clue, size)
        return tuple(dict.fromkeys(cell for cell, _ in (*premises, conclusion)))
    raise ClueValidationError(f'Not an extension clue: {clue.kind!r}')


def evaluate(clue: Clue, full_assignment: Mapping[CellId, bool], size: int) -> bool:
    """Direct semantics; never calls the encoder or a solver."""
    if clue.kind == 'PARITY':
        cells, odd = parse_parity(clue, size)
        target = parse_target_status(clue)
        return sum(full_assignment[cell] == target for cell in cells) % 2 == odd
    if clue.kind == 'CONNECTED':
        cells, target = parse_connected(clue, size)
        active = {cell for cell in cells if full_assignment[cell] == target}
        return _is_orthogonally_connected(active)
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


def encode_connected(cells: tuple[CellId, ...], lits: tuple[int, ...], pool: AuxPool,
                     direct_limit: int = DIRECT_CLAUSE_LIMIT) -> list[Clause]:
    """Direct exclusion of disconnected assignments when 2^n clauses fit, otherwise a
    reachability encoding: one root, and every active cell is reached from it in < n steps."""
    n = len(cells)
    if 2 ** n <= direct_limit:
        clauses: list[Clause] = []
        for bits in product((False, True), repeat=n):
            active = {cell for cell, bit in zip(cells, bits) if bit}
            if not _is_orthogonally_connected(active):
                clauses.append(tuple(-lit if bit else lit for lit, bit in zip(lits, bits)))
        return clauses
    coords = [(ord(cell[0]) - 65, int(cell[1:]) - 1) for cell in cells]
    nbrs = [[j for j, (x, y) in enumerate(coords) if abs(x - cx) + abs(y - cy) == 1]
            for cx, cy in coords]
    roots = [pool.new() for _ in range(n)]
    clauses = [(-r, a) for r, a in zip(roots, lits)]  # the root is an active cell
    clauses += [(-roots[i], -roots[j]) for i in range(n) for j in range(i + 1, n)]
    clauses += [(-a, *roots) for a in lits]  # any active cell -> some root
    # reach[i] at step d: cell i is within d steps of the root through active cells
    reach = roots
    for _ in range(n - 1):
        step = [pool.new() for _ in range(n)]
        for i, x in enumerate(step):
            clauses += [(-x, lits[i]), (-x, reach[i], *(reach[j] for j in nbrs[i]))]
        reach = step
    clauses += [(-a, x) for a, x in zip(lits, reach)]  # every active cell is reached
    return clauses


def encode_compound(premises: tuple[int, ...], conclusion: int) -> list[Clause]:
    """(p1 AND ... AND pm) -> q as one clause; dropped when tautological."""
    clause = tuple(dict.fromkeys((*(-lit for lit in premises), conclusion)))
    if any(-lit in clause for lit in clause):
        return []
    return [clause]
