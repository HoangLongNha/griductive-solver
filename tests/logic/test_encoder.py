"""Task 2.2 acceptance tests: CNF encoder for the six core clues and KB_t."""
import json
from itertools import product
from math import comb
from pathlib import Path
import random

import pytest

import fixture_oracle
from cnf_check import assert_clue_equivalent, assert_lits_equivalent, satisfies
from griductive.game.engine import GameSession, load_puzzle
from griductive.logic import cnf_counts, encode_clue, encode_full_clues, encode_kb
from griductive.logic.cardinality import AuxPool, at_least, at_most, exactly
from griductive.models import Clue, Inference, Status, var_to_cell

ROOT = Path(__file__).resolve().parents[2]
TUTORIAL = str(ROOT / 'puzzles/3x3/tutorial_3x3.json')
VALID = sorted((ROOT / 'puzzles').glob('[34]x[34]/*.json'))


def clue(kind, **data):
    return Clue('c', kind, data)


def encode(c, size=3):
    pool = AuxPool(size * size)
    return encode_clue(c, size, pool), pool


class AcceptAll:
    """Fake oracle proving whatever the test asks for (engine checks the hidden truth)."""
    def __init__(self):
        self.answer = Inference.UNKNOWN

    def classify_one(self, state, cell):
        return self.answer


# CNF-01 -------------------------------------------------------------------

def test_cnf01_binary_clues_have_textbook_clauses():
    # A1 = 1, B1 = 2 on a 3x3 board
    assert encode(clue('SAME', cells=['A1', 'B1']))[0] == [(-1, 2), (1, -2)]
    assert encode(clue('DIFFERENT', cells=['A1', 'B1']))[0] == [(1, 2), (-1, -2)]
    assert encode(clue('FACT', cell='C3', status='CRIMINAL'))[0] == [(9,)]
    assert encode(clue('FACT', cell='B2', status='INNOCENT'))[0] == [(-5,)]


# CNF-02 -------------------------------------------------------------------

@pytest.mark.parametrize('kind', ['EXACTLY', 'AT_LEAST', 'AT_MOST'])
@pytest.mark.parametrize('region', [
    {'type': 'row', 'index': 2}, {'type': 'column', 'index': 'C'},
    {'type': 'neighbors', 'cell': 'B2'}, {'type': 'neighbors', 'cell': 'A1'},
    {'type': 'cells', 'cells': ['C3', 'A1', 'B2', 'C1']},
], ids=lambda r: f"{r['type']}-{r.get('index', r.get('cell', len(r.get('cells', ()))))}")
def test_cnf02_counting_equivalent_to_evaluator(kind, region):
    n = len(fixture_oracle.region_cells(region, 3))
    for k in range(n + 1):
        c = clue(kind, k=k, region=region)
        clauses, pool = encode(c)
        assert pool.aux_count == 0  # small regions use the direct encoding
        assert_clue_equivalent(c, 3, clauses, 9)


@pytest.mark.parametrize('n', range(1, 8))
def test_cnf02_sequential_counter_equivalent_for_every_k(n):
    lits = tuple(range(1, n + 1))
    for k in range(n + 1):
        for encode_fn, ok in ((at_most, lambda b: sum(b) <= k), (at_least, lambda b: sum(b) >= k),
                              (exactly, lambda b: sum(b) == k)):
            clauses = encode_fn(lits, k, AuxPool(n), direct_limit=0)
            assert_lits_equivalent(clauses, n, ok)


def test_cnf02_cardinality_handles_negative_literals():
    lits = (1, -2, 3)  # count of {x1, not x2, x3}
    clauses = exactly(lits, 2, AuxPool(3))
    for bits in product((False, True), repeat=3):
        count = bits[0] + (not bits[1]) + bits[2]
        assert satisfies(clauses, dict(zip((1, 2, 3), bits))) == (count == 2)


# CNF-03 -------------------------------------------------------------------

def test_cnf03_initial_kb_has_only_revealed_clue_and_unit():
    game = GameSession(load_puzzle(TUTORIAL), AcceptAll())
    cnf = encode_kb(game.snapshot())
    # A1 revealed as CRIMINAL (unit 1); its clue "B1 is innocent" -> (-2)
    assert cnf.clauses == ((1,), (-2,))
    assert (cnf.primary_count, cnf.variable_count) == (9, 9)


def test_cnf03_kb_grows_with_accepted_verdicts_only():
    oracle = AcceptAll()
    game = GameSession(load_puzzle(TUTORIAL), oracle)
    oracle.answer = Inference.INNOCENT
    game.submit_verdict('B1', Status.INNOCENT)
    oracle.answer = Inference.UNKNOWN
    rejected = game.submit_verdict('C1', Status.INNOCENT)  # NOT_PROVABLE: no reveal
    public = game.snapshot()
    assert rejected.newly_revealed is None
    cnf = encode_kb(public)
    pool = AuxPool(9)
    expected = [(1,), (-2,)]  # units for every proved verdict first
    for card in public.cards:
        if card.revealed:
            expected += encode_clue(card.clue, 3, pool)
    assert cnf.clauses == tuple(expected)
    # Hidden clue of C1 (DIFFERENT C1, A2) is absent.
    assert (3, 4) not in cnf.clauses and (-3, -4) not in cnf.clauses


def test_cnf03_hidden_data_does_not_change_kb(tmp_path):
    """Two puzzles differing only in a face-down card's clue give the same KB."""
    raw = json.loads(Path(TUTORIAL).read_text())
    raw['cards'][8]['clue'] = {'id': 'c-C3', 'kind': 'FACT', 'cell': 'A1', 'status': 'CRIMINAL'}
    other = tmp_path / 'other.json'
    other.write_text(json.dumps(raw))
    original = GameSession(load_puzzle(TUTORIAL), AcceptAll()).snapshot()
    changed = GameSession(load_puzzle(str(other)), AcceptAll()).snapshot()
    assert encode_kb(original) == encode_kb(changed)


# CNF-04 -------------------------------------------------------------------

def test_cnf04_counts_tutorial_full_clue_set():
    cnf = encode_full_clues(load_puzzle(TUTORIAL))
    # FACT 1 + SAME 2 + DIFF 2 + FACT 1 + EXACTLY(2,3) 4 + EXACTLY(2,3) 4
    # + DIFF 2 + AT_MOST(1,3) C(3,2)=3 + AT_LEAST(1,3) C(3,3)=1
    assert cnf_counts(cnf) == {'primary_count': 9, 'aux_count': 0, 'clause_count': 20}


def test_cnf04_auxiliary_counts_match_sequential_counter():
    cells = [var_to_cell(v, 5) for v in range(1, 26)]
    big = clue('EXACTLY', k=12, region={'type': 'cells', 'cells': cells})
    clauses, pool = encode(big, 5)
    n, k_most, k_least = 25, 12, 13  # at_least 12 == at_most 13 of negations
    assert pool.aux_count == (n - 1) * k_most + (n - 1) * k_least
    seq = lambda k: 1 + (k - 1) + (n - 2) * (2 * k + 1) + 1
    assert len(clauses) == seq(k_most) + seq(k_least)
    used = {abs(lit) for clause in clauses for lit in clause}
    assert used == set(range(1, 25 + pool.aux_count + 1))


def test_cnf04_direct_encoding_sizes():
    center = {'type': 'neighbors', 'cell': 'B2'}  # 8 cells
    for k in range(9):
        clauses, pool = encode(clue('AT_MOST', k=k, region=center))
        assert len(clauses) == (comb(8, k + 1) if k < 8 else 0) and pool.aux_count == 0


# CNF-05 -------------------------------------------------------------------

@pytest.mark.parametrize('path', VALID, ids=lambda p: p.stem)
def test_cnf05_full_clue_models_match_independent_enumeration(path):
    puzzle = load_puzzle(str(path))
    raw = json.loads(path.read_text())
    cnf = encode_full_clues(puzzle)
    assert cnf.variable_count == cnf.primary_count  # fixtures need no auxiliaries
    expected = list(fixture_oracle.full_clue_models(raw))
    cells = [var_to_cell(v, puzzle.size) for v in range(1, puzzle.size ** 2 + 1)]
    expected_bits = {tuple(m[c] for c in cells) for m in expected}
    for bits in product((False, True), repeat=len(cells)):
        model = dict(zip(range(1, len(cells) + 1), bits))
        assert satisfies(cnf.clauses, model) == (bits in expected_bits)


@pytest.mark.parametrize('size', [3, 4, 5])
def test_cnf05_random_generated_clues_are_encoded_automatically(size):
    rng = random.Random(77 + size)
    cells = [var_to_cell(v, size) for v in range(1, size * size + 1)]
    for _ in range(60):
        kind = rng.choice(['FACT', 'SAME', 'DIFFERENT', 'EXACTLY', 'AT_LEAST', 'AT_MOST'])
        if kind == 'FACT':
            c = clue(kind, cell=rng.choice(cells), status=rng.choice(['CRIMINAL', 'INNOCENT']))
        elif kind in ('SAME', 'DIFFERENT'):
            c = clue(kind, cells=rng.sample(cells, 2))
        else:
            region = {'type': 'cells', 'cells': rng.sample(cells, rng.randint(1, 9))}
            c = clue(kind, k=rng.randint(0, len(region['cells'])), region=region)
        clauses, _ = encode(c, size)
        assert_clue_equivalent(c, size, clauses, size * size)
