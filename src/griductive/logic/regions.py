"""Clue regions and shared parameter parsing (task 2.1). No SAT or encoder dependency."""
from collections.abc import Mapping

from griductive.models import CellId, Region, cell_to_var


class ClueValidationError(ValueError):
    """A clue parameter or referenced region is invalid for the board."""


def field(data: Mapping, key: str):
    if not isinstance(data, Mapping) or key not in data:
        raise ClueValidationError(f'Clue is missing field {key!r}')
    return data[key]


def parse_status(value) -> bool:
    """'CRIMINAL' -> True, 'INNOCENT' -> False (also accepts `Status`)."""
    if value == 'CRIMINAL':
        return True
    if value == 'INNOCENT':
        return False
    raise ClueValidationError(f'Invalid status {value!r}')


def parse_literal(item: Mapping, size: int) -> tuple[CellId, bool]:
    """A `{cell, status}` mapping as (cell, is_criminal)."""
    return check_cell(field(item, 'cell'), size), parse_status(field(item, 'status'))


def check_size(size: int) -> int:
    if type(size) is not int or not 1 <= size <= 26:
        raise ClueValidationError('Board size must be an integer in 1..26')
    return size


def check_cell(cell: CellId, size: int) -> CellId:
    try:
        cell_to_var(cell, size)
    except ValueError as exc:
        raise ClueValidationError(f'Invalid cell {cell!r} for a {size}x{size} board') from exc
    return cell


def region_from_data(data: Region | Mapping) -> Region:
    """Convert a clue's `region` mapping (puzzle schema v1) to a `Region`."""
    if isinstance(data, Region):
        return data
    if not isinstance(data, Mapping):
        raise ClueValidationError('Region must be a mapping')
    kind = data.get('type')
    if kind in ('row', 'column'):
        return Region(kind, index=data.get('index'))
    if kind == 'neighbors':
        return Region(kind, cell=data.get('cell'))
    if kind == 'cells':
        cells = data.get('cells')
        if not isinstance(cells, (list, tuple)):
            raise ClueValidationError('Explicit region needs a list of cells')
        return Region(kind, cells=tuple(cells))
    raise ClueValidationError(f'Unknown region type {kind!r}')


def resolve_region(region: Region | Mapping, size: int) -> tuple[CellId, ...]:
    """Return the region's distinct cells; rows/columns/neighbors in row-major order.

    Explicit `cells` regions keep their listed order. Empty, duplicate or
    off-board regions raise `ClueValidationError`.
    """
    region = region_from_data(region)
    check_size(size)
    if region.type == 'row':
        if type(region.index) is not int or not 1 <= region.index <= size:
            raise ClueValidationError(f'Row {region.index!r} outside board')
        cells = tuple(f'{chr(65 + c)}{region.index}' for c in range(size))
    elif region.type == 'column':
        index = region.index
        if not (isinstance(index, str) and len(index) == 1 and 'A' <= index < chr(65 + size)):
            raise ClueValidationError(f'Column {index!r} outside board')
        cells = tuple(f'{index}{r}' for r in range(1, size + 1))
    elif region.type == 'neighbors':
        center = check_cell(region.cell, size)
        x, y = ord(center[0]) - 65, int(center[1:]) - 1
        cells = tuple(f'{chr(65 + c)}{r + 1}' for r in range(size) for c in range(size)
                      if max(abs(c - x), abs(r - y)) == 1)
    elif region.type == 'cells':
        cells = tuple(check_cell(cell, size) for cell in region.cells)
        if not cells:
            raise ClueValidationError('Explicit region must not be empty')
        if len(set(cells)) != len(cells):
            raise ClueValidationError('Explicit region contains duplicate cells')
    else:
        raise ClueValidationError(f'Unknown region type {region.type!r}')
    return cells
