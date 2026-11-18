"""Task 2.1 acceptance tests: regions, clue validation and direct evaluator."""
from itertools import product
from pathlib import Path
import random

import pytest

import fixture_oracle
from griductive.game.loader import load_puzzle
from griductive.logic import (ClueValidationError, evaluate_clue, referenced_cells,
                              resolve_region, validate_clue)
from griductive.models import Clue, Region, var_to_cell

ROOT = Path(__file__).resolve().parents[2]
VALID = sorted((ROOT / 'puzzles').glob('[34]x[34]/*.json'))


def board(size):
    return [var_to_cell(v, size) for v in range(1, size * size + 1)]


def clue(kind, **data):
    return Clue('c', kind, data)


def random_core_clue(rng, size):
    cells = board(size)
    kind = rng.choice(['FACT', 'SAME', 'DIFFERENT', 'EXACTLY', 'AT_LEAST', 'AT_MOST'])
    if kind == 'FACT':
        return {'kind': kind, 'cell': rng.choice(cells), 'status': rng.choice(['CRIMINAL', 'INNOCENT'])}
    if kind in ('SAME', 'DIFFERENT'):
        return {'kind': kind, 'cells': rng.sample(cells, 2)}
    region = rng.choice([
        {'type': 'row', 'index': rng.randint(1, size)},
        {'type': 'column', 'index': chr(65 + rng.randrange(size))},
        {'type': 'neighbors', 'cell': rng.choice(cells)},
        {'type': 'cells', 'cells': rng.sample(cells, rng.randint(1, len(cells)))},
    ])
    n = len(fixture_oracle.region_cells(region, size))
    return {'kind': kind, 'k': rng.randint(0, n), 'region': region}


# SEM-01 -------------------------------------------------------------------

@pytest.mark.parametrize('path', VALID, ids=lambda p: p.stem)
def test_sem01_every_clue_true_under_hidden_solution(path):
    puzzle = load_puzzle(str(path))
    solution = {card.cell: card.hidden_status.value == 'CRIMINAL' for card in puzzle.cards}
    for card in puzzle.cards:
        if card.clue.kind in ('PARITY', 'COMPOUND'):
            continue  # extensions arrive in task 2.3
        assert evaluate_clue(card.clue, solution, puzzle.size)


def test_sem01_core_clues_match_truth_tables():
    a = {'A1': True, 'B1': False, 'C1': True, 'A2': False, 'B2': False, 'C2': True,
         'A3': True, 'B3': True, 'C3': False}
    row1 = {'type': 'row', 'index': 1}  # A1, B1, C1 -> 2 criminals
    assert evaluate_clue(clue('FACT', cell='A1', status='CRIMINAL'), a, 3)
    assert not evaluate_clue(clue('FACT', cell='A1', status='INNOCENT'), a, 3)
    assert evaluate_clue(clue('SAME', cells=['A1', 'C1']), a, 3)
    assert not evaluate_clue(clue('SAME', cells=['A1', 'B1']), a, 3)
    assert evaluate_clue(clue('DIFFERENT', cells=['A1', 'B1']), a, 3)
    assert not evaluate_clue(clue('DIFFERENT', cells=['B1', 'A2']), a, 3)
    assert evaluate_clue(clue('EXACTLY', k=2, region=row1), a, 3)
    assert not evaluate_clue(clue('EXACTLY', k=1, region=row1), a, 3)
    assert evaluate_clue(clue('AT_LEAST', k=2, region=row1), a, 3)
    assert not evaluate_clue(clue('AT_LEAST', k=3, region=row1), a, 3)
    assert evaluate_clue(clue('AT_MOST', k=2, region=row1), a, 3)
    assert not evaluate_clue(clue('AT_MOST', k=1, region=row1), a, 3)


@pytest.mark.parametrize('size', [3, 4])
def test_sem01_random_clues_agree_with_independent_oracle(size):
    rng = random.Random(2026 + size)
    for _ in range(400):
        raw = random_core_clue(rng, size)
        assignment = {cell: rng.random() < 0.5 for cell in board(size)}
        data = {k: v for k, v in raw.items() if k != 'kind'}
        expected = fixture_oracle.evaluate(raw, assignment, size)
        assert evaluate_clue(Clue('c', raw['kind'], data), assignment, size) == expected


def test_sem01_evaluator_rejects_partial_assignment():
    with pytest.raises(ValueError):
        evaluate_clue(clue('SAME', cells=['A1', 'B1']), {'A1': True}, 3)


# SEM-02 -------------------------------------------------------------------

@pytest.mark.parametrize('size,center,expected', [
    (3, 'B2', 8), (3, 'B1', 5), (3, 'A2', 5), (3, 'A1', 3), (3, 'C3', 3),
    (4, 'B2', 8), (4, 'C3', 8), (4, 'D2', 5), (4, 'D4', 3), (5, 'C3', 8),
])
def test_sem02_neighbor_counts_exclude_self(size, center, expected):
    cells = resolve_region({'type': 'neighbors', 'cell': center}, size)
    assert len(cells) == expected and center not in cells
    x, y = ord(center[0]), int(center[1:])
    assert all(max(abs(ord(c[0]) - x), abs(int(c[1:]) - y)) == 1 for c in cells)


def test_sem02_neighbors_of_corner_are_row_major():
    assert resolve_region(Region('neighbors', cell='A1'), 3) == ('B1', 'A2', 'B2')


# SEM-03 -------------------------------------------------------------------

def test_sem03_rows_and_columns_follow_coordinates():
    assert resolve_region({'type': 'row', 'index': 2}, 3) == ('A2', 'B2', 'C2')
    assert resolve_region({'type': 'column', 'index': 'D'}, 4) == ('D1', 'D2', 'D3', 'D4')
    assert resolve_region(Region('row', index=4), 4) == ('A4', 'B4', 'C4', 'D4')


def test_sem03_empty_region_rejected_for_every_type():
    # On a 1x1 board A1 has no neighbors; the region must not silently be empty.
    with pytest.raises(ClueValidationError):
        resolve_region({'type': 'neighbors', 'cell': 'A1'}, 1)
    with pytest.raises(ClueValidationError):
        validate_clue(clue('EXACTLY', k=0, region={'type': 'neighbors', 'cell': 'A1'}), 1)
    assert resolve_region({'type': 'row', 'index': 1}, 1) == ('A1',)


def test_sem03_explicit_cells_keep_order_and_must_be_distinct():
    assert resolve_region({'type': 'cells', 'cells': ['C3', 'A1']}, 3) == ('C3', 'A1')
    with pytest.raises(ClueValidationError):
        resolve_region({'type': 'cells', 'cells': ['A1', 'A1']}, 3)
    with pytest.raises(ClueValidationError):
        resolve_region({'type': 'cells', 'cells': []}, 3)


@pytest.mark.parametrize('region', [
    {'type': 'row', 'index': 0}, {'type': 'row', 'index': 4}, {'type': 'row', 'index': True},
    {'type': 'row', 'index': '1'}, {'type': 'column', 'index': 'D'},
    {'type': 'column', 'index': 'a'}, {'type': 'column', 'index': 'AB'},
    {'type': 'neighbors', 'cell': 'D1'}, {'type': 'neighbors', 'cell': 'A0'},
    {'type': 'cells', 'cells': ['A1', 'A4']}, {'type': 'cells', 'cells': 'A1'},
    {'type': 'diagonal', 'index': 1}, 'row 1',
])
def test_sem03_invalid_regions_are_rejected(region):
    with pytest.raises(ClueValidationError):
        resolve_region(region, 3)


# SEM-04 -------------------------------------------------------------------

@pytest.mark.parametrize('kind', ['EXACTLY', 'AT_LEAST', 'AT_MOST'])
def test_sem04_k_bounds(kind):
    row = {'type': 'row', 'index': 1}
    for k in (0, 3):
        validate_clue(clue(kind, k=k, region=row), 3)
    for k in (4, -1, True, 1.0, None):
        with pytest.raises(ClueValidationError):
            validate_clue(clue(kind, k=k, region=row), 3)


def test_sem04_boundary_k_semantics():
    row = {'type': 'row', 'index': 1}
    for bits in product((False, True), repeat=3):
        a = dict(zip(('A1', 'B1', 'C1'), bits))
        count = sum(bits)
        assert evaluate_clue(clue('EXACTLY', k=0, region=row), a, 3) == (count == 0)
        assert evaluate_clue(clue('EXACTLY', k=3, region=row), a, 3) == (count == 3)
        assert evaluate_clue(clue('AT_LEAST', k=0, region=row), a, 3)
        assert evaluate_clue(clue('AT_MOST', k=3, region=row), a, 3)


@pytest.mark.parametrize('bad', [
    clue('FACT', cell='Z9', status='CRIMINAL'), clue('FACT', cell='A1', status='GUILTY'),
    clue('FACT', cell='A1'), clue('SAME', cells=['A1', 'A1']), clue('SAME', cells=['A1']),
    clue('DIFFERENT', cells=['A1', 'B1', 'C1']), clue('DIFFERENT', cells=['A1', 'D1']),
    clue('EXACTLY', k=1), clue('AT_MOST', region={'type': 'row', 'index': 1}),
    clue('LIAR', cells=['A1', 'B1']),
])
def test_sem04_invalid_clue_parameters_are_rejected(bad):
    with pytest.raises(ClueValidationError):
        validate_clue(bad, 3)


# SEM-05 -------------------------------------------------------------------

def test_sem05_names_professions_and_owner_status_do_not_matter():
    puzzle = load_puzzle(str(ROOT / 'puzzles/3x3/tutorial_3x3.json'))
    solution = {card.cell: card.hidden_status.value == 'CRIMINAL' for card in puzzle.cards}
    # A1 (Alice) is a CRIMINAL, yet her clue "B1 is innocent" is true.
    owner = puzzle.cards[0]
    assert owner.hidden_status.value == 'CRIMINAL'
    assert evaluate_clue(owner.clue, solution, 3)
    # Flipping the owner's own status leaves a clue about other cells unchanged.
    assert evaluate_clue(owner.clue, {**solution, 'A1': False}, 3)
    # Clues only reference cell IDs; names/professions are not inputs.
    assert referenced_cells(owner.clue, 3) == ('B1',)
