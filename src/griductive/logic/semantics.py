"""Clue validation and direct semantic evaluation (task 2.1).

`evaluate_clue` decides a clue on a complete assignment by counting/comparing
statuses directly; it never calls the CNF encoder or a SAT solver. A clue is
judged true or false by its content only: the owner's status, name and
profession play no role (revealed clues are always true).
"""
from collections.abc import Mapping

from griductive.models import CellId, Clue
from . import extensions
from .regions import (ClueValidationError, check_cell, check_size, field, parse_literal,
                      parse_status, resolve_region)

CORE_KINDS = ('FACT', 'SAME', 'DIFFERENT', 'EXACTLY', 'AT_LEAST', 'AT_MOST')
COUNTING_KINDS = ('EXACTLY', 'AT_LEAST', 'AT_MOST')
SUPPORTED_KINDS = CORE_KINDS + extensions.EXTENSION_KINDS


def parse_pair(clue: Clue, size: int) -> tuple[CellId, CellId]:
    cells = field(clue.data, 'cells')
    if not isinstance(cells, (list, tuple)) or len(cells) != 2:
        raise ClueValidationError(f'{clue.kind} needs exactly two cells')
    left, right = (check_cell(cell, size) for cell in cells)
    if left == right:
        raise ClueValidationError(f'{clue.kind} needs two distinct cells')
    return left, right


def parse_target_status(clue: Clue) -> bool:
    """Target status counted by a clue; defaults to True ('CRIMINAL')."""
    if 'status' not in clue.data:
        return True
    return parse_status(clue.data['status'])


def parse_counting(clue: Clue, size: int) -> tuple[tuple[CellId, ...], int]:
    cells = resolve_region(field(clue.data, 'region'), size)
    parse_target_status(clue)
    k = field(clue.data, 'k')
    if type(k) is not int or not 0 <= k <= len(cells):
        raise ClueValidationError(f'k={k!r} must be an integer in 0..{len(cells)}')
    return cells, k


def check_clue(clue: Clue, size: int) -> None:
    if not isinstance(clue, Clue):
        raise ClueValidationError('Expected a Clue')
    check_size(size)
    if clue.kind not in SUPPORTED_KINDS:
        raise ClueValidationError(f'Unsupported clue kind {clue.kind!r}')


def referenced_cells(clue: Clue, size: int) -> tuple[CellId, ...]:
    """Cells the clue talks about or counts (e.g. for GUI highlighting)."""
    check_clue(clue, size)
    if clue.kind == 'FACT':
        return (parse_literal(clue.data, size)[0],)
    if clue.kind in ('SAME', 'DIFFERENT'):
        return parse_pair(clue, size)
    if clue.kind in extensions.EXTENSION_KINDS:
        return extensions.referenced_cells(clue, size)
    return parse_counting(clue, size)[0]


def validate_clue(clue: Clue, size: int) -> None:
    """Raise `ClueValidationError` if the clue's parameters or region are invalid."""
    referenced_cells(clue, size)


def evaluate_clue(clue: Clue, full_assignment: Mapping[CellId, bool], size: int) -> bool:
    """Is the clue true under a complete assignment (True = Criminal)?"""
    cells = referenced_cells(clue, size)
    for cell in cells:
        if type(full_assignment.get(cell)) is not bool:
            raise ValueError(f'Assignment has no boolean status for {cell}')
    if clue.kind == 'FACT':
        cell, criminal = parse_literal(clue.data, size)
        return full_assignment[cell] == criminal
    if clue.kind in ('SAME', 'DIFFERENT'):
        left, right = cells
        return (full_assignment[left] == full_assignment[right]) == (clue.kind == 'SAME')
    if clue.kind in extensions.EXTENSION_KINDS:
        return extensions.evaluate(clue, full_assignment, size)
    target = parse_target_status(clue)
    count = sum(full_assignment[cell] == target for cell in cells)
    k = parse_counting(clue, size)[1]
    return {'EXACTLY': count == k, 'AT_LEAST': count >= k, 'AT_MOST': count <= k}[clue.kind]
