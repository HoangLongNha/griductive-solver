"""KB_t examples handed to VT1/VT4: the shared 1.3a walk-through and extension clues
that change a conclusion. Entailment here uses the test-only `cnf_check.classify`
check (KB |= l  iff  KB AND -l is UNSAT), not the production DPLL."""
from pathlib import Path

from cnf_check import classify
from griductive.game.engine import GameSession, load_puzzle
from griductive.logic import encode_kb
from griductive.models import Clue, Inference, PublicCard, PublicState, Status, var_to_cell

ROOT = Path(__file__).resolve().parents[2]


def public(revealed):
    """3x3 PublicState; `revealed` maps cell -> (status, clue)."""
    cards = []
    for v in range(1, 10):
        cell = var_to_cell(v, 3)
        status, clue = revealed.get(cell, (None, None))
        cards.append(PublicCard(cell, f'P{v}', 'X', cell in revealed, status, clue))
    return PublicState('example', 3, tuple(cards))


class Oracle:
    answer = Inference.UNKNOWN

    def classify_one(self, state, cell):
        return self.answer


def test_shared_13a_walkthrough():
    oracle = Oracle()
    game = GameSession(load_puzzle(str(ROOT / 'puzzles/3x3/tutorial_3x3.json')), oracle)
    kb0 = encode_kb(game.snapshot())
    assert kb0.clauses == ((1,), (-2,))                       # step 1
    assert classify(kb0, 2) == 'INNOCENT'                      # step 2: KB AND (2) UNSAT
    assert classify(kb0, 3) == 'UNKNOWN'                       # step 3: hidden c-B1 not used
    oracle.answer = Inference.INNOCENT
    assert game.submit_verdict('B1', Status.INNOCENT).newly_revealed == 'B1'  # step 4
    kb1 = encode_kb(game.snapshot())
    assert {(-2, 3), (2, -3)} <= set(kb1.clauses)              # step 5: SAME(B1, C1)
    assert classify(kb1, 3) == 'INNOCENT'


def test_parity_clue_forces_a_verdict():
    row1_odd = Clue('p', 'PARITY', {'parity': 'ODD', 'region': {'type': 'row', 'index': 1}})
    filler = Clue('f', 'FACT', {'cell': 'A1', 'status': 'CRIMINAL'})
    with_parity = public({'A1': (Status.CRIMINAL, row1_odd), 'B1': (Status.INNOCENT, filler)})
    without = public({'A1': (Status.CRIMINAL, filler), 'B1': (Status.INNOCENT, filler)})
    # A1 criminal + B1 innocent + odd row 1  =>  C1 innocent
    assert classify(encode_kb(with_parity), 3) == 'INNOCENT'
    assert classify(encode_kb(without), 3) == 'UNKNOWN'


def test_compound_clue_forces_a_verdict():
    rule = Clue('x', 'COMPOUND', {'premises': [{'cell': 'A1', 'status': 'CRIMINAL'},
                                               {'cell': 'B1', 'status': 'INNOCENT'}],
                                  'conclusion': {'cell': 'C1', 'status': 'CRIMINAL'}})
    filler = Clue('f', 'FACT', {'cell': 'A1', 'status': 'CRIMINAL'})
    with_rule = public({'A1': (Status.CRIMINAL, rule), 'B1': (Status.INNOCENT, filler)})
    premise_false = public({'A1': (Status.CRIMINAL, rule), 'B1': (Status.CRIMINAL, filler)})
    assert classify(encode_kb(with_rule), 3) == 'CRIMINAL'
    assert classify(encode_kb(premise_false), 3) == 'UNKNOWN'  # no modus ponens


def test_inconsistent_public_kb_is_detected():
    clash = Clue('f', 'FACT', {'cell': 'A1', 'status': 'INNOCENT'})
    kb = encode_kb(public({'A1': (Status.CRIMINAL, clash)}))
    assert classify(kb, 2) == 'INCONSISTENT'
