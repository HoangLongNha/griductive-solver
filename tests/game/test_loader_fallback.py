"""The stdlib schema fallback (no jsonschema installed) must accept/reject exactly like jsonschema."""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

jsonschema = pytest.importorskip('jsonschema')

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / 'schemas/puzzle.schema.json').read_text(encoding='utf-8'))
PUZZLES = sorted(ROOT.glob('puzzles/*/*.json'))
BASE = json.loads((ROOT / 'puzzles/3x3/tutorial_3x3.json').read_text(encoding='utf-8'))


@pytest.fixture(scope='module')
def fallback(monkeypatch_module):
    """A separate copy of loader.py imported while jsonschema is unavailable."""
    monkeypatch_module.setitem(sys.modules, 'jsonschema', None)
    path = ROOT / 'src/griductive/game/loader.py'
    spec = importlib.util.spec_from_file_location('loader_without_jsonschema', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.Draft202012Validator is not jsonschema.Draft202012Validator
    return module


@pytest.fixture(scope='module')
def monkeypatch_module():
    with pytest.MonkeyPatch.context() as mp:
        yield mp


def with_region(region):
    raw = copy.deepcopy(BASE)
    raw['cards'][0]['clue'] = {'id': 'c-x', 'kind': 'EXACTLY', 'k': 1, 'region': region}
    return raw


def with_field(key, value):
    raw = copy.deepcopy(BASE)
    raw[key] = value
    return raw


def with_clue(clue):
    raw = copy.deepcopy(BASE)
    raw['cards'][0]['clue'] = clue
    return raw


ROW = {'type': 'row', 'index': 1}
COL = {'type': 'column', 'index': 'A'}
CASES = {
    'intersection-ok': with_region({'type': 'intersection', 'regions': [ROW, COL]}),
    'intersection-sub-extra-field': with_region(
        {'type': 'intersection', 'regions': [ROW, {**COL, 'unexpected': 1}]}),
    'intersection-sub-bad-type': with_region({'type': 'intersection', 'regions': [ROW, {'type': 'diagonal'}]}),
    'intersection-nested': with_region(
        {'type': 'intersection', 'regions': [ROW, {'type': 'intersection', 'regions': [ROW, COL]}]}),
    'intersection-sub-not-object': with_region({'type': 'intersection', 'regions': [ROW, 'A1']}),
    'intersection-one-region': with_region({'type': 'intersection', 'regions': [ROW]}),
    'cells-unhashable-item': with_region({'type': 'cells', 'cells': [['A1']]}),
    'cells-duplicate': with_region({'type': 'cells', 'cells': ['A1', 'A1']}),
    'between-unhashable-item': with_region({'type': 'between', 'cells': [{}, 'A1']}),
    'between-same-cell': with_region({'type': 'between', 'cells': ['A1', 'A1']}),
    'row-bool-index': with_region({'type': 'row', 'index': True}),
    'initial-revealed-object': with_field('initial_revealed', [{}]),
    'initial-revealed-list': with_field('initial_revealed', [['A1']]),
    'initial-revealed-duplicate': with_field('initial_revealed', ['A1', 'A1']),
    'initial-revealed-empty': with_field('initial_revealed', []),
    'same-unhashable-cell': with_clue({'id': 'c-x', 'kind': 'SAME', 'cells': [{}, 'B1']}),
}


def fallback_accepts(fallback, raw):
    return next(fallback.Draft202012Validator(SCHEMA).iter_errors(raw), None) is None


@pytest.mark.parametrize('raw', list(CASES.values()), ids=list(CASES))
def test_fallback_schema_matches_jsonschema(fallback, raw):
    assert fallback_accepts(fallback, raw) == jsonschema.Draft202012Validator(SCHEMA).is_valid(raw)


@pytest.mark.parametrize('path', PUZZLES, ids=lambda p: p.stem)
def test_fallback_schema_matches_jsonschema_on_repository_puzzles(fallback, path):
    raw = json.loads(path.read_text(encoding='utf-8'))
    assert fallback_accepts(fallback, raw) == jsonschema.Draft202012Validator(SCHEMA).is_valid(raw)


@pytest.mark.parametrize('name', ['initial-revealed-object', 'intersection-sub-extra-field',
                                  'between-unhashable-item'])
def test_fallback_loader_raises_puzzle_validation_error(fallback, tmp_path, name):
    path = tmp_path / 'p.json'
    path.write_text(json.dumps(CASES[name]), encoding='utf-8')
    with pytest.raises(fallback.PuzzleValidationError):
        fallback.load_puzzle(str(path))
