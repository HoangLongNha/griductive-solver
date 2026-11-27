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


def _cell_coords(cell: CellId, size: int) -> tuple[int, int]:
    check_cell(cell, size)
    return ord(cell[0]) - 65, int(cell[1:]) - 1


def _check_pair(cells_raw, size: int, kind: str) -> tuple[CellId, CellId]:
    if not isinstance(cells_raw, (list, tuple)) or len(cells_raw) != 2:
        raise ClueValidationError(f'{kind} region needs exactly two cells')
    a, b = check_cell(cells_raw[0], size), check_cell(cells_raw[1], size)
    if a == b:
        raise ClueValidationError(f'{kind} region needs two distinct cells')
    return a, b


def region_from_data(data: Region | Mapping) -> Region:
    """Convert a clue's `region` mapping (puzzle schema v1 + spatial extensions) to a `Region`."""
    if isinstance(data, Region):
        return data
    if not isinstance(data, Mapping):
        raise ClueValidationError('Region must be a mapping')
    kind = data.get('type')
    if kind in ('row', 'column'):
        return Region(kind, index=data.get('index'))
    if kind in ('neighbors', 'above', 'below', 'left_of', 'right_of'):
        return Region(kind, cell=data.get('cell'))
    if kind in ('cells', 'between', 'common_neighbors'):
        cells = data.get('cells')
        if not isinstance(cells, (list, tuple)):
            raise ClueValidationError(f'{kind} region needs a list of cells')
        return Region(kind, cells=tuple(cells))
    if kind in ('corners', 'edges', 'boundary'):
        return Region(kind)
    if kind == 'intersection':
        sub = data.get('regions')
        if not isinstance(sub, (list, tuple)) or len(sub) < 2:
            raise ClueValidationError('intersection region needs at least two sub-regions')
        return Region(kind, cells=tuple(region_from_data(r) for r in sub))
    raise ClueValidationError(f'Unknown region type {kind!r}')


def resolve_region(region: Region | Mapping, size: int) -> tuple[CellId, ...]:
    """Return the region's distinct cells; spatial regions in row-major order.

    Explicit `cells` regions keep their listed order. Empty (of any type),
    duplicate or off-board regions raise `ClueValidationError`.
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
        x, y = _cell_coords(region.cell, size)
        cells = tuple(f'{chr(65 + c)}{r + 1}' for r in range(size) for c in range(size)
                      if max(abs(c - x), abs(r - y)) == 1)
    elif region.type == 'above':
        x, y = _cell_coords(region.cell, size)
        cells = tuple(f'{chr(65 + x)}{r + 1}' for r in range(0, y))
    elif region.type == 'below':
        x, y = _cell_coords(region.cell, size)
        cells = tuple(f'{chr(65 + x)}{r + 1}' for r in range(y + 1, size))
    elif region.type == 'left_of':
        x, y = _cell_coords(region.cell, size)
        cells = tuple(f'{chr(65 + c)}{y + 1}' for c in range(0, x))
    elif region.type == 'right_of':
        x, y = _cell_coords(region.cell, size)
        cells = tuple(f'{chr(65 + c)}{y + 1}' for c in range(x + 1, size))
    elif region.type == 'corners':
        last_col = chr(65 + size - 1)
        raw_corners = ('A1', f'{last_col}1', f'A{size}', f'{last_col}{size}')
        cells = tuple(dict.fromkeys(raw_corners))
    elif region.type in ('edges', 'boundary'):
        cells = tuple(
            f'{chr(65 + c)}{r + 1}'
            for r in range(size)
            for c in range(size)
            if r in (0, size - 1) or c in (0, size - 1)
        )
    elif region.type == 'between':
        a, b = _check_pair(region.cells, size, 'between')
        ax, ay = _cell_coords(a, size)
        bx, by = _cell_coords(b, size)
        if ay == by:
            lo, hi = min(ax, bx), max(ax, bx)
            cells = tuple(f'{chr(65 + c)}{ay + 1}' for c in range(lo + 1, hi))
        elif ax == bx:
            lo, hi = min(ay, by), max(ay, by)
            cells = tuple(f'{chr(65 + ax)}{r + 1}' for r in range(lo + 1, hi))
        else:
            raise ClueValidationError('between region requires two cells in the same row or column')
    elif region.type == 'common_neighbors':
        a, b = _check_pair(region.cells, size, 'common_neighbors')
        na = resolve_region(Region('neighbors', cell=a), size)
        nb = set(resolve_region(Region('neighbors', cell=b), size))
        cells = tuple(c for c in na if c in nb)
    elif region.type == 'intersection':
        if not region.cells or len(region.cells) < 2:
            raise ClueValidationError('intersection region needs at least two sub-regions')
        resolved = [resolve_region(sub, size) for sub in region.cells]
        keep = set(resolved[1])
        for extra in resolved[2:]:
            keep &= set(extra)
        cells = tuple(c for c in resolved[0] if c in keep)
    elif region.type == 'cells':
        cells = tuple(check_cell(cell, size) for cell in region.cells)
        if len(set(cells)) != len(cells):
            raise ClueValidationError('Explicit region contains duplicate cells')
    else:
        raise ClueValidationError(f'Unknown region type {region.type!r}')
    if not cells:  # e.g. explicit [] or the neighbors of A1 on a 1x1 board
        raise ClueValidationError(f'{region.type} region resolves to no cells')
    return cells
