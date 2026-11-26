"""Private puzzle loading and semantic validation (no SAT dependency)."""
from dataclasses import dataclass
import json
from pathlib import Path
import re

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:  # pragma: no cover - stdlib fallback when optional jsonschema is missing
    _CELL_RE = re.compile(r'^[A-Z][1-9][0-9]*$')
    _ID_RE = re.compile(r'^[a-z][a-z0-9_]*$')

    @dataclass(frozen=True)
    class _SchemaError:
        absolute_path: tuple[object, ...]
        message: str

    class Draft202012Validator:  # type: ignore[no-redef]
        def __init__(self, schema: dict) -> None:
            self.schema = schema

        def iter_errors(self, raw: object):
            if not isinstance(raw, dict):
                yield _SchemaError((), 'Puzzle must be a JSON object')
                return
            required = {'schema_version', 'id', 'size', 'initial_revealed', 'cards'}
            if set(raw) != required:
                yield _SchemaError((), 'Top-level keys must match schema v1')
                return
            if type(raw['schema_version']) is not int or raw['schema_version'] != 1:
                yield _SchemaError(('schema_version',), 'schema_version must be 1')
            if not isinstance(raw['id'], str) or not _ID_RE.match(raw['id']):
                yield _SchemaError(('id',), 'Invalid puzzle id')
            if type(raw['size']) is not int or not (3 <= raw['size'] <= 5):
                yield _SchemaError(('size',), 'size must be an integer in 3..5')
            init = raw['initial_revealed']
            if (not isinstance(init, list) or not init or len(set(init)) != len(init)
                    or not all(isinstance(x, str) and _CELL_RE.match(x) for x in init)):
                yield _SchemaError(('initial_revealed',), 'Invalid initial_revealed list')
            cards = raw['cards']
            if not isinstance(cards, list) or len(cards) < 9:
                yield _SchemaError(('cards',), 'cards must be a list of at least 9 items')
                return
            for idx, card in enumerate(cards):
                if not isinstance(card, dict) or set(card) != {'cell', 'name', 'profession', 'hidden_status', 'clue'}:
                    yield _SchemaError(('cards', idx), 'Invalid card keys')
                    continue
                if not isinstance(card['cell'], str) or not _CELL_RE.match(card['cell']):
                    yield _SchemaError(('cards', idx, 'cell'), 'Invalid cell id')
                if not isinstance(card['name'], str) or not card['name']:
                    yield _SchemaError(('cards', idx, 'name'), 'Invalid name')
                if not isinstance(card['profession'], str) or not card['profession']:
                    yield _SchemaError(('cards', idx, 'profession'), 'Invalid profession')
                if card['hidden_status'] not in ('CRIMINAL', 'INNOCENT'):
                    yield _SchemaError(('cards', idx, 'hidden_status'), 'Invalid hidden_status')
                clue = card['clue']
                if not isinstance(clue, dict) or not isinstance(clue.get('id'), str) or not clue.get('id'):
                    yield _SchemaError(('cards', idx, 'clue'), 'Invalid clue')
                    continue
                kind = clue.get('kind')
                if kind == 'FACT':
                    if (set(clue) != {'id', 'kind', 'cell', 'status'}
                            or not isinstance(clue.get('cell'), str) or not _CELL_RE.match(clue['cell'])
                            or clue.get('status') not in ('CRIMINAL', 'INNOCENT')):
                        yield _SchemaError(('cards', idx, 'clue'), 'Invalid FACT clue')
                elif kind in ('SAME', 'DIFFERENT'):
                    cells = clue.get('cells')
                    if (set(clue) != {'id', 'kind', 'cells'} or not isinstance(cells, list)
                            or len(cells) != 2 or len(set(cells)) != 2
                            or not all(isinstance(x, str) and _CELL_RE.match(x) for x in cells)):
                        yield _SchemaError(('cards', idx, 'clue'), f'Invalid {kind} clue')
                elif kind == 'COMPOUND':
                    prems, conc = clue.get('premises'), clue.get('conclusion')
                    if (set(clue) != {'id', 'kind', 'premises', 'conclusion'}
                            or not isinstance(prems, list) or not (1 <= len(prems) <= 8)
                            or not isinstance(conc, dict)):
                        yield _SchemaError(('cards', idx, 'clue'), 'Invalid COMPOUND clue')
                    else:
                        for item in [*prems, conc]:
                            if (not isinstance(item, dict) or set(item) != {'cell', 'status'}
                                    or not isinstance(item.get('cell'), str) or not _CELL_RE.match(item['cell'])
                                    or item.get('status') not in ('CRIMINAL', 'INNOCENT')):
                                yield _SchemaError(('cards', idx, 'clue'), 'Invalid COMPOUND literal')
                elif kind in ('EXACTLY', 'AT_LEAST', 'AT_MOST', 'PARITY', 'CONNECTED'):
                    req_keys = {'id', 'kind', 'region'}
                    if kind == 'PARITY':
                        req_keys.add('parity')
                    elif kind != 'CONNECTED':
                        req_keys.add('k')
                    allowed_keys = req_keys | {'status'}
                    if not (req_keys <= set(clue) <= allowed_keys):
                        yield _SchemaError(('cards', idx, 'clue'), f'Invalid {kind} keys')
                        continue
                    if 'status' in clue and clue.get('status') not in ('CRIMINAL', 'INNOCENT'):
                        yield _SchemaError(('cards', idx, 'clue', 'status'), 'Invalid status')
                    if kind == 'PARITY' and clue.get('parity') not in ('ODD', 'EVEN'):
                        yield _SchemaError(('cards', idx, 'clue', 'parity'), 'Invalid parity')
                    if kind in ('EXACTLY', 'AT_LEAST', 'AT_MOST') and (
                        type(clue.get('k')) is not int or clue['k'] < 0
                    ):
                        yield _SchemaError(('cards', idx, 'clue', 'k'), 'Invalid k')
                    reg = clue.get('region')
                    if not isinstance(reg, dict) or not isinstance(reg.get('type'), str):
                        yield _SchemaError(('cards', idx, 'clue', 'region'), 'Invalid region')
                        continue
                    rtype = reg.get('type')
                    if rtype == 'row':
                        if set(reg) != {'type', 'index'} or type(reg.get('index')) is not int or reg['index'] < 1:
                            yield _SchemaError(('cards', idx, 'clue', 'region'), 'Invalid row region')
                    elif rtype == 'column':
                        if (set(reg) != {'type', 'index'} or not isinstance(reg.get('index'), str)
                                or not re.match(r'^[A-Z]$', reg['index'])):
                            yield _SchemaError(('cards', idx, 'clue', 'region'), 'Invalid column region')
                    elif rtype in ('neighbors', 'above', 'below', 'left_of', 'right_of'):
                        if (set(reg) != {'type', 'cell'} or not isinstance(reg.get('cell'), str)
                                or not _CELL_RE.match(reg['cell'])):
                            yield _SchemaError(('cards', idx, 'clue', 'region'), f'Invalid {rtype} region')
                    elif rtype in ('between', 'common_neighbors'):
                        rcells = reg.get('cells')
                        if (set(reg) != {'type', 'cells'} or not isinstance(rcells, list)
                                or len(rcells) != 2 or len(set(rcells)) != 2
                                or not all(isinstance(x, str) and _CELL_RE.match(x) for x in rcells)):
                            yield _SchemaError(('cards', idx, 'clue', 'region'), f'Invalid {rtype} region')
                    elif rtype in ('corners', 'edges'):
                        if set(reg) != {'type'}:
                            yield _SchemaError(('cards', idx, 'clue', 'region'), f'Invalid {rtype} region')
                    elif rtype == 'intersection':
                        sub = reg.get('regions')
                        if set(reg) != {'type', 'regions'} or not isinstance(sub, list) or len(sub) < 2:
                            yield _SchemaError(('cards', idx, 'clue', 'region'), 'Invalid intersection region')
                    elif rtype == 'cells':
                        rcells = reg.get('cells')
                        if (set(reg) != {'type', 'cells'} or not isinstance(rcells, list) or not rcells
                                or len(set(rcells)) != len(rcells)
                                or not all(isinstance(x, str) and _CELL_RE.match(x) for x in rcells)):
                            yield _SchemaError(('cards', idx, 'clue', 'region'), 'Invalid cells region')
                    else:
                        yield _SchemaError(('cards', idx, 'clue', 'region'), 'Invalid region type')
                else:
                    yield _SchemaError(('cards', idx, 'clue', 'kind'), 'Invalid clue kind')

        def validate(self, raw: object) -> None:
            err = next(self.iter_errors(raw), None)
            if err is not None:
                raise ValueError(f'{list(err.absolute_path)}: {err.message}')

from griductive.logic.regions import resolve_region
from griductive.logic.semantics import evaluate_clue
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
    try:
        return resolve_region(region, size)
    except ValueError as exc:
        raise PuzzleValidationError(str(exc)) from exc


def _clue_is_true(clue, assignment, size):
    """Validate hidden integrity directly; independent of encoder and solver."""
    try:
        model_clue = Clue(
            clue['id'],
            clue['kind'],
            {k: v for k, v in clue.items() if k not in ('id', 'kind')},
        )
        return evaluate_clue(model_clue, assignment, size)
    except ValueError as exc:
        raise PuzzleValidationError(str(exc)) from exc


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
