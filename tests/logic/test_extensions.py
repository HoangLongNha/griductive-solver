"""Task 2.3 acceptance tests: PARITY and COMPOUND extensions."""
from itertools import product
from pathlib import Path

import pytest

from cnf_check import assert_clue_equivalent, assert_lits_equivalent
from griductive.game.loader import load_puzzle
from griductive.logic import ClueValidationError, encode_clue, evaluate_clue, validate_clue
from griductive.logic.cardinality import AuxPool
from griductive.logic.extensions import encode_compound, encode_parity
from griductive.models import Clue

ROOT = Path(__file__).resolve().parents[2]
ROW1 = {'type': 'row', 'index': 1}


def clue(kind, **data):
    return Clue('c', kind, data)


def lit(cell, status):
    return {'cell': cell, 'status': status}


# EXT-01 -------------------------------------------------------------------

@pytest.mark.parametrize('criminals', [0, 1, 2, 3])
def test_ext01_parity_by_number_of_criminals(criminals):
    a = {cell: i < criminals for i, cell in enumerate(('A1', 'B1', 'C1'))}
    a.update({c: True for c in ('A2', 'B2', 'C2', 'A3', 'B3', 'C3')})  # outside region
    assert evaluate_clue(clue('PARITY', parity='ODD', region=ROW1), a, 3) == (criminals % 2 == 1)
    assert evaluate_clue(clue('PARITY', parity='EVEN', region=ROW1), a, 3) == (criminals % 2 == 0)


@pytest.mark.parametrize('n', range(1, 7))
@pytest.mark.parametrize('odd', [True, False])
@pytest.mark.parametrize('direct_limit', [256, 0], ids=['direct', 'tseitin'])
def test_ext01_parity_cnf_both_encodings(n, odd, direct_limit):
    pool = AuxPool(n)
    clauses = encode_parity(tuple(range(1, n + 1)), odd, pool, direct_limit)
    assert_lits_equivalent(clauses, n, lambda bits: sum(bits) % 2 == odd)
    assert pool.aux_count == (0 if direct_limit else n - 1)


# EXT-02 -------------------------------------------------------------------

def test_ext02_compound_truth_table():
    c = clue('COMPOUND', premises=[lit('A1', 'CRIMINAL'), lit('B1', 'INNOCENT')],
             conclusion=lit('C1', 'CRIMINAL'))
    for p1, p2, q in product((False, True), repeat=3):
        a = {'A1': p1, 'B1': not p2, 'C1': q}
        assert evaluate_clue(c, a, 3) == ((not (p1 and p2)) or q)
    assert encode_clue(c, 3, AuxPool(9)) == [(-1, 2, 3)]


def test_ext02_compound_degenerate_literals():
    assert encode_compound((1, 1), 2) == [(-1, 2)]  # repeated premise
    assert encode_compound((1, -1), 2) == []        # contradictory premises: always true
    assert encode_compound((1,), 1) == []           # p -> p
    assert encode_compound((1,), -1) == [(-1,)]     # p -> not p  ==  not p


# EXT-03 -------------------------------------------------------------------

@pytest.mark.parametrize('c', [
    clue('PARITY', parity='ODD', region={'type': 'neighbors', 'cell': 'B2'}),
    clue('PARITY', parity='EVEN', region={'type': 'column', 'index': 'A'}),
    clue('PARITY', parity='ODD', region={'type': 'cells', 'cells': ['C3']}),
    clue('COMPOUND', premises=[lit('A1', 'CRIMINAL')], conclusion=lit('B2', 'INNOCENT')),
    clue('COMPOUND', premises=[lit('A1', 'INNOCENT'), lit('B1', 'CRIMINAL'), lit('C3', 'CRIMINAL')],
         conclusion=lit('A1', 'CRIMINAL')),
    clue('COMPOUND', premises=[lit('A1', 'CRIMINAL'), lit('A1', 'INNOCENT')],
         conclusion=lit('B1', 'CRIMINAL')),
], ids=['parity-neighbors', 'parity-column', 'parity-single', 'compound-1', 'compound-3',
        'compound-contradictory'])
def test_ext03_extension_cnf_semantically_equivalent(c):
    clauses = encode_clue(c, 3, AuxPool(9))
    assert_clue_equivalent(c, 3, clauses, 9)


def test_ext03_large_parity_uses_auxiliaries_and_stays_equivalent():
    cells = [f'{chr(65 + c)}{r}' for r in range(1, 5) for c in range(4)][:10]
    c = clue('PARITY', parity='ODD', region={'type': 'cells', 'cells': cells})
    pool = AuxPool(16)
    clauses = encode_clue(c, 4, pool)
    assert pool.aux_count == 9  # 2^9 > 256 direct clauses -> XOR chain
    assert_clue_equivalent(c, 4, clauses, 16)


@pytest.mark.parametrize('bad', [
    clue('PARITY', parity='odd', region=ROW1), clue('PARITY', region=ROW1),
    clue('PARITY', parity='ODD', region={'type': 'row', 'index': 9}),
    clue('COMPOUND', premises=[], conclusion=lit('A1', 'CRIMINAL')),
    clue('COMPOUND', premises=[lit('A1', 'GUILTY')], conclusion=lit('B1', 'CRIMINAL')),
    clue('COMPOUND', premises=[lit('A1', 'CRIMINAL')], conclusion=lit('Z1', 'CRIMINAL')),
    clue('COMPOUND', premises=[lit('A1', 'CRIMINAL')]),
])
def test_ext03_invalid_extension_parameters(bad):
    with pytest.raises(ClueValidationError):
        validate_clue(bad, 3)


# EXT-04 -------------------------------------------------------------------

def test_ext04_extension_clues_true_regardless_of_owner():
    puzzle = load_puzzle(str(ROOT / 'puzzles/3x3/extensions_3x3.json'))
    solution = {card.cell: card.hidden_status.value == 'CRIMINAL' for card in puzzle.cards}
    owners = {card.clue.kind: card for card in puzzle.cards}
    # PARITY owned by a criminal (B3), COMPOUND owned by an innocent (C3): both true.
    assert owners['PARITY'].hidden_status.value == 'CRIMINAL'
    assert owners['COMPOUND'].hidden_status.value == 'INNOCENT'
    for card in puzzle.cards:
        assert evaluate_clue(card.clue, solution, 3)
