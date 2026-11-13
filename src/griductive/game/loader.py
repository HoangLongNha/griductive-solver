"""Private puzzle loading and semantic validation (no SAT dependency)."""
from dataclasses import dataclass
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from griductive.models import Clue, Status, cell_to_var, var_to_cell


class PuzzleValidationError(ValueError):
    """Puzzle structure, references, or hidden assignment are invalid."""


@dataclass(frozen=True)
class PrivateCard:
    cell: str
    name: str
    profession: str
    hidden_status: Status
    clue: Clue


@dataclass(frozen=True)
class Puzzle:
    id: str
    size: int
    cards: tuple[PrivateCard, ...]
    initial_revealed: tuple[str, ...]


def _region_cells(region, size):
    kind = region['type']
    if kind == 'row':
        if not 1 <= region['index'] <= size:
            raise PuzzleValidationError('Row outside board')
        cells = [f'{chr(65+c)}{region["index"]}' for c in range(size)]
    elif kind == 'column':
        cells = [f'{region["index"]}{r}' for r in range(1, size+1)]
    elif kind == 'cells':
        cells = region['cells']
    else:
        center = region['cell']
        cell_to_var(center, size)
        x, y = ord(center[0])-65, int(center[1:])-1
        cells = [f'{chr(65+c)}{r+1}' for r in range(size) for c in range(size)
                 if max(abs(c-x), abs(r-y)) == 1]
    for cell in cells:
        cell_to_var(cell, size)
    if not cells or len(set(cells)) != len(cells):
        raise PuzzleValidationError('Region must contain distinct cells')
    return tuple(cells)


def _clue_is_true(clue, assignment, size):
    """Validate hidden integrity directly; independent of encoder and solver."""
    kind = clue['kind']
    def literal(value):
        cell_to_var(value['cell'], size)
        return assignment[value['cell']] == (value['status'] == 'CRIMINAL')
    if kind == 'FACT':
        return literal(clue)
    if kind in ('SAME', 'DIFFERENT'):
        left, right = clue['cells']
        cell_to_var(left, size)
        cell_to_var(right, size)
        return (assignment[left] == assignment[right]) == (kind == 'SAME')
    if kind == 'COMPOUND':
        # Validate every reference even when the implication short-circuits.
        premises = [literal(p) for p in clue['premises']]
        conclusion = literal(clue['conclusion'])
        return not all(premises) or conclusion
    cells = _region_cells(clue['region'], size)
    count = sum(assignment[cell] for cell in cells)
    if kind == 'PARITY':
        return count % 2 == (clue['parity'] == 'ODD')
    k = clue['k']
    if not 0 <= k <= len(cells):
        raise PuzzleValidationError('k outside region cardinality')
    return {'EXACTLY': count == k, 'AT_LEAST': count >= k,
            'AT_MOST': count <= k}[kind]


def load_puzzle(path: str) -> Puzzle:
    """Read repository schema v1; uniqueness/playability are separate checks.

    Filesystem errors propagate as OSError. Malformed JSON and invalid puzzles
    raise PuzzleValidationError. Diagnostic fixtures with false clues are rejected.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding='utf-8'))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise PuzzleValidationError('Invalid UTF-8 puzzle JSON') from exc
    schema_path = Path(__file__).resolve().parents[3] / 'schemas/puzzle.schema.json'
    schema = json.loads(schema_path.read_text(encoding='utf-8'))
    error = next(Draft202012Validator(schema).iter_errors(raw), None)
    if error:
        raise PuzzleValidationError(f'{list(error.absolute_path)}: {error.message}')
    try:
        size, cards = raw['size'], raw['cards']
        expected = tuple(var_to_cell(v, size) for v in range(1, size*size+1))
        if len(cards) != size*size or {c['cell'] for c in cards} != set(expected):
            raise PuzzleValidationError('Board must contain each cell exactly once')
        by_cell = {c['cell']: c for c in cards}
        ordered = [by_cell[cell] for cell in expected]
        names = [c['name'] for c in ordered]
        if len(set(names)) != len(names):
            raise PuzzleValidationError('Duplicate character name')
        clue_ids = [c['clue']['id'] for c in cards]
        if len(set(clue_ids)) != len(clue_ids):
            raise PuzzleValidationError('Duplicate clue ID')
        if not set(raw['initial_revealed']) <= set(expected):
            raise PuzzleValidationError('Initial reveal outside board')
        assignment = {c['cell']: c['hidden_status'] == 'CRIMINAL' for c in cards}
        for card in ordered:
            if not _clue_is_true(card['clue'], assignment, size):
                raise PuzzleValidationError(f'Clue {card["clue"]["id"]} contradicts hidden solution')
        return Puzzle(raw['id'], size, tuple(
            PrivateCard(c['cell'], c['name'], c['profession'], Status(c['hidden_status']),
                        Clue(c['clue']['id'], c['clue']['kind'],
                             {k: v for k, v in c['clue'].items() if k not in ('id', 'kind')}))
            for c in ordered), tuple(raw['initial_revealed']))
    except ValueError as exc:
        if isinstance(exc, PuzzleValidationError):
            raise
        raise PuzzleValidationError(str(exc)) from exc
