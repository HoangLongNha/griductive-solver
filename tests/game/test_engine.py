"""Game boundary acceptance tests using an injected fake, not a SAT solver."""
import json
from pathlib import Path

import pytest

from griductive.game.engine import (GameSession, PuzzleIntegrityError,
                                   PuzzleValidationError, load_puzzle)
from griductive.models import Inference, Status, VerdictStatus, SolverTimeout

ROOT = Path(__file__).resolve().parents[2]


class FakeVerdictOracle:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def classify_one(self, state, cell):
        self.calls.append((state, cell))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def raw():
    return json.loads((ROOT / 'puzzles/3x3/tutorial_3x3.json').read_text())


@pytest.fixture
def puzzle():
    return load_puzzle(str(ROOT / 'puzzles/3x3/tutorial_3x3.json'))


def save(tmp_path, raw):
    path = tmp_path / 'puzzle.json'
    path.write_text(json.dumps(raw), encoding='utf-8')
    return str(path)


def hidden(puzzle):
    return next(c for c in puzzle.cards if c.cell not in puzzle.initial_revealed)


def test_ge01_snapshot_private_and_detached(puzzle):
    game = GameSession(puzzle, FakeVerdictOracle(Inference.UNKNOWN))
    first, second = game.snapshot(), game.snapshot()
    assert first == second and first is not second
    for card, other, private in zip(first.cards, second.cards, puzzle.cards):
        assert not hasattr(card, 'hidden_status')
        if card.revealed:
            assert card.clue is not private.clue and card.clue is not other.clue
            assert card.clue.data is not private.clue.data
            with pytest.raises(TypeError):
                card.clue.data['new'] = 'bad'
        else:
            assert card.clue is None and card.known_status is None


def test_ge02_accept_only_one_and_public_oracle(puzzle):
    target = hidden(puzzle)
    oracle = FakeVerdictOracle(Inference(target.hidden_status.value))
    game = GameSession(puzzle, oracle)
    before = game.snapshot()
    result = game.submit_verdict(target.cell, target.hidden_status)
    assert result.outcome == VerdictStatus.ACCEPTED
    assert result.newly_revealed == target.cell
    assert sum(c.revealed for c in result.state.cards) == len(puzzle.initial_revealed)+1
    assert oracle.calls == [(before, target.cell)]
    assert next(c for c in before.cards if c.cell == target.cell).clue is None
    assert next(c for c in result.state.cards if c.cell == target.cell).clue == target.clue


@pytest.mark.parametrize('inference,outcome', [
    (Inference.UNKNOWN, VerdictStatus.NOT_PROVABLE),
    (Inference.INCONSISTENT, VerdictStatus.INCONSISTENT),
])
def test_ge03_rejection_unchanged(puzzle, inference, outcome):
    game = GameSession(puzzle, FakeVerdictOracle(inference))
    target = hidden(puzzle)
    before = game.snapshot()
    result = game.submit_verdict(target.cell, target.hidden_status)
    assert result.outcome == outcome and result.newly_revealed is None
    assert game.snapshot() == before == result.state


def test_ge03_opposite_forced(puzzle):
    target = hidden(puzzle)
    game = GameSession(puzzle, FakeVerdictOracle(Inference(target.hidden_status.value)))
    wrong = Status.INNOCENT if target.hidden_status == Status.CRIMINAL else Status.CRIMINAL
    before = game.snapshot()
    assert game.submit_verdict(target.cell, wrong).outcome == VerdictStatus.CONTRADICTED
    assert game.snapshot() == before


def test_ge04_restart(puzzle):
    target = hidden(puzzle)
    game = GameSession(puzzle, FakeVerdictOracle(Inference(target.hidden_status.value)))
    initial = game.snapshot()
    game.submit_verdict(target.cell, target.hidden_status)
    assert game.restart() == initial
    assert game.restart() == initial


@pytest.mark.parametrize('failure', ['integrity', 'timeout', 'invalid', 'revealed', 'status'])
def test_errors_do_not_mutate(puzzle, failure):
    target = hidden(puzzle)
    opposite = Status.INNOCENT if target.hidden_status == Status.CRIMINAL else Status.CRIMINAL
    oracle = FakeVerdictOracle(SolverTimeout() if failure == 'timeout' else Inference(opposite.value))
    game = GameSession(puzzle, oracle)
    before = game.snapshot()
    cell = 'Z99' if failure == 'invalid' else puzzle.initial_revealed[0] if failure == 'revealed' else target.cell
    status = 'CRIMINAL' if failure == 'status' else opposite
    error = SolverTimeout if failure == 'timeout' else PuzzleIntegrityError if failure == 'integrity' else ValueError
    with pytest.raises(error):
        game.submit_verdict(cell, status)
    assert game.snapshot() == before


@pytest.mark.parametrize('case', ['duplicate', 'missing', 'reference', 'initial', 'name', 'clue_id', 'k', 'false', 'row', 'column', 'neighbor', 'compound', 'schema'])
def test_ge05_invalid_puzzles(raw, tmp_path, case):
    if case == 'duplicate': raw['cards'][1]['cell'] = raw['cards'][0]['cell']
    elif case == 'missing': raw['cards'].pop()
    elif case == 'initial': raw['initial_revealed'] = ['Z99']
    elif case == 'name': raw['cards'][1]['name'] = raw['cards'][0]['name']
    elif case == 'clue_id': raw['cards'][1]['clue']['id'] = raw['cards'][0]['clue']['id']
    elif case == 'schema': raw['size'] = True
    else:
        clue = {'id': 'replacement', 'kind': 'FACT', 'cell': 'Z99', 'status': 'CRIMINAL'}
        if case == 'false':
            clue['cell'] = raw['cards'][0]['cell']
            clue['status'] = 'INNOCENT' if raw['cards'][0]['hidden_status'] == 'CRIMINAL' else 'CRIMINAL'
        elif case in ('k', 'row', 'column', 'neighbor'):
            region = {'type': 'cells', 'cells': ['A1']}
            if case == 'row': region = {'type': 'row', 'index': 4}
            if case == 'column': region = {'type': 'column', 'index': 'Z'}
            if case == 'neighbor': region = {'type': 'neighbors', 'cell': 'Z99'}
            clue = {'id': 'replacement', 'kind': 'EXACTLY', 'k': 99 if case == 'k' else 0, 'region': region}
        elif case == 'compound':
            clue = {'id': 'replacement', 'kind': 'COMPOUND',
                    'premises': [{'cell': 'A1', 'status': 'INNOCENT'}],
                    'conclusion': {'cell': 'Z99', 'status': 'CRIMINAL'}}
        raw['cards'][0]['clue'] = clue
    with pytest.raises(PuzzleValidationError):
        load_puzzle(save(tmp_path, raw))


@pytest.mark.parametrize('path', sorted((ROOT / 'puzzles').glob('[34]x[34]/*.json')))
def test_valid_fixtures(path):
    puzzle = load_puzzle(str(path))
    assert len(puzzle.cards) == puzzle.size**2


def test_json_errors(tmp_path):
    path = tmp_path / 'invalid.json'
    path.write_text('{')
    with pytest.raises(PuzzleValidationError):
        load_puzzle(str(path))


def test_nested_snapshot_and_sessions_are_independent(tmp_path, raw):
    # An explicit region produces nested mappings and sequences in a public clue.
    raw['initial_revealed'] = [raw['cards'][0]['cell']]
    raw['cards'][0]['clue'] = {
        'id': 'nested', 'kind': 'EXACTLY',
        'region': {'type': 'cells', 'cells': ['A1']},
        'k': int(raw['cards'][0]['hidden_status'] == 'CRIMINAL'),
    }
    puzzle = load_puzzle(save(tmp_path, raw))
    oracle = FakeVerdictOracle(Inference(hidden(puzzle).hidden_status.value))
    first, second = GameSession(puzzle, oracle), GameSession(puzzle, oracle)
    public = first.snapshot()
    nested = public.cards[0].clue.data['region']
    assert nested is not puzzle.cards[0].clue.data['region']
    assert nested['cells'] == ('A1',)
    with pytest.raises(TypeError):
        nested['cells'][0] = 'B1'
    with pytest.raises(TypeError):
        nested['type'] = 'row'
    target = hidden(puzzle)
    first.submit_verdict(target.cell, target.hidden_status)
    assert second.snapshot() == public
    assert public.cards[0].clue.data['region']['cells'] == ('A1',)


def test_loader_canonicalizes_card_order(tmp_path, raw):
    raw['cards'].reverse()
    puzzle = load_puzzle(save(tmp_path, raw))
    assert [card.cell for card in puzzle.cards][:4] == ['A1', 'B1', 'C1', 'A2']
