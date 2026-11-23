from pathlib import Path

import pytest

from griductive.game import controller
from griductive.logic import encode_kb
from griductive.models import Status, VerdictStatus


TUTORIAL = Path(__file__).resolve().parents[2] / 'puzzles/3x3/tutorial_3x3.json'


def card_at(state, cell):
    return next(card for card in state.cards if card.cell == cell)


def test_slice_load_only_reveals_a1_and_preserves_game_on_failure(tmp_path):
    game = controller.Controller()
    initial = game.load(TUTORIAL)
    assert [card.cell for card in initial.cards if card.revealed] == ['A1']
    for cell in ('B1', 'C1'):
        card = card_at(initial, cell)
        assert card.known_status is None and card.clue is None
    with pytest.raises(FileNotFoundError):
        game.load(tmp_path / 'missing.json')
    assert game.snapshot() == initial


def test_slice_dpll_proves_b1_and_engine_reveals_only_b1():
    game = controller.Controller()
    initial = game.load(TUTORIAL)
    clue = card_at(initial, 'A1').clue
    assert (clue.id, clue.kind, dict(clue.data)) == (
        'c-A1', 'FACT', {'cell': 'B1', 'status': 'INNOCENT'},
    )

    result = game.step()
    assert result.outcome == VerdictStatus.ACCEPTED and result.newly_revealed == 'B1'
    assert [card.cell for card in result.state.cards if card.revealed] == ['A1', 'B1']
    assert card_at(result.state, 'B1').clue.id == 'c-B1'
    assert card_at(result.state, 'C1').clue is None
    assert card_at(result.state, 'C1').known_status is None
    assert encode_kb(result.state).clauses == ((1,), (-2,), (-2,), (-2, 3), (2, -3))

    trace = game.last_trace
    assert trace.active_clue_ids == ('c-A1',)
    assert trace.cnf.clauses == ((1,), (-2,))
    assert trace.newly_revealed_clue_id == 'c-B1'
    assert any(q.assumptions == (2,) and not q.is_sat for q in trace.queries)
    assert sum(q.purpose.value == 'VERDICT_RECHECK' for q in trace.queries) == 2


def test_slice_rejected_verdicts_preserve_snapshot_and_kb_and_restart():
    game = controller.Controller()
    initial = game.load(TUTORIAL)
    initial_kb = encode_kb(initial)
    for cell, status, outcome in (
        ('C1', Status.INNOCENT, VerdictStatus.NOT_PROVABLE),
        ('B1', Status.CRIMINAL, VerdictStatus.CONTRADICTED),
    ):
        result = game.submit_verdict(cell, status)
        assert result.outcome == outcome and result.newly_revealed is None
        assert result.state == game.snapshot() == initial
        assert encode_kb(result.state) == initial_kb
        assert game.last_trace.newly_revealed_clue_id is None
    assert game.submit_verdict('B1', Status.INNOCENT).outcome == VerdictStatus.ACCEPTED
    assert game.restart() == initial
    assert game.last_trace is None
