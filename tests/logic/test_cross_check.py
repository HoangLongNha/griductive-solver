"""Task 2.4: exhaustive evaluator-vs-CNF cross-check and negative validation tests."""
from pathlib import Path

import pytest

from cnf_check import assert_clue_equivalent
from griductive.game.engine import GameSession, load_puzzle
from griductive.logic import ClueValidationError, encode_clue, encode_kb, resolve_region
from griductive.logic.cardinality import AuxPool
from griductive.models import Clue, PublicCard, PublicState, Status, var_to_cell


def all_regions(size):
    cells = [var_to_cell(v, size) for v in range(1, size * size + 1)]
    yield from ({'type': 'row', 'index': r} for r in range(1, size + 1))
    yield from ({'type': 'column', 'index': chr(65 + c)} for c in range(size))
    yield from ({'type': 'neighbors', 'cell': cell} for cell in cells)
    yield {'type': 'cells', 'cells': cells[::2][:6]}


def all_small_clues(size):
    cells = [var_to_cell(v, size) for v in range(1, size * size + 1)]
    for cell in cells:
        for status in ('CRIMINAL', 'INNOCENT'):
            yield Clue('f', 'FACT', {'cell': cell, 'status': status})
    for i, a in enumerate(cells):
        for b in cells[i + 1:]:
            yield Clue('s', 'SAME', {'cells': [a, b]})
            yield Clue('d', 'DIFFERENT', {'cells': [a, b]})
    for region in all_regions(size):
        n = len(resolve_region(region, size))
        for kind in ('EXACTLY', 'AT_LEAST', 'AT_MOST'):
            for k in range(n + 1):
                yield Clue('k', kind, {'k': k, 'region': region})
        for parity in ('ODD', 'EVEN'):
            yield Clue('p', 'PARITY', {'parity': parity, 'region': region})
    for a, b, c in zip(cells, cells[1:], cells[2:]):
        yield Clue('x', 'COMPOUND', {'premises': [{'cell': a, 'status': 'CRIMINAL'},
                                                  {'cell': b, 'status': 'INNOCENT'}],
                                     'conclusion': {'cell': c, 'status': 'CRIMINAL'}})


# VER-01 -------------------------------------------------------------------

@pytest.mark.parametrize('size', [3, 4])
def test_ver01_every_small_clue_cnf_iff_evaluator(size):
    checked = 0
    for clue in all_small_clues(size):
        clauses = encode_clue(clue, size, AuxPool(size * size))
        assert_clue_equivalent(clue, size, clauses, size * size)
        checked += 1
    assert checked > 300


# VER-03 -------------------------------------------------------------------

@pytest.mark.parametrize('bad', [
    Clue('b', 'FACT', {'cell': 'D4', 'status': 'CRIMINAL'}),
    Clue('b', 'SAME', {'cells': ['B2', 'B2']}),
    Clue('b', 'DIFFERENT', {'cells': ['A1']}),
    Clue('b', 'EXACTLY', {'k': 4, 'region': {'type': 'row', 'index': 1}}),
    Clue('b', 'AT_LEAST', {'k': -1, 'region': {'type': 'column', 'index': 'A'}}),
    Clue('b', 'AT_MOST', {'k': 1, 'region': {'type': 'neighbors', 'cell': 'A4'}}),
    Clue('b', 'EXACTLY', {'k': 0, 'region': {'type': 'cells', 'cells': []}}),
    Clue('b', 'PARITY', {'parity': 'ODD', 'region': {'type': 'column', 'index': 'Z'}}),
    Clue('b', 'COMPOUND', {'premises': [], 'conclusion': {'cell': 'A1', 'status': 'CRIMINAL'}}),
    Clue('b', 'NO', {'region': {'type': 'row', 'index': 1}}),
])
def test_ver03_encoder_rejects_invalid_parameters(bad):
    with pytest.raises(ClueValidationError):
        encode_clue(bad, 3, AuxPool(9))


def test_ver03_invalid_revealed_clue_in_kb_is_rejected():
    bad = Clue('b', 'EXACTLY', {'k': 5, 'region': {'type': 'row', 'index': 1}})
    cards = tuple(PublicCard(var_to_cell(v, 3), f'P{v}', 'X', v == 1,
                             Status.CRIMINAL if v == 1 else None, bad if v == 1 else None)
                  for v in range(1, 10))
    with pytest.raises(ClueValidationError):
        encode_kb(PublicState('bad', 3, cards))


def test_ver03_encoding_is_deterministic():
    class Never:
        def classify_one(self, state, cell):
            raise AssertionError('not called')
    path = Path(__file__).resolve().parents[2] / 'puzzles/3x3/extensions_3x3.json'
    first = encode_kb(GameSession(load_puzzle(str(path)), Never()).snapshot())
    second = encode_kb(GameSession(load_puzzle(str(path)), Never()).snapshot())
    assert first == second
