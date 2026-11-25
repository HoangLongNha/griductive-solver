"""Production integration: real Engine, encoder, DPLL, Agent and HTTP adapter."""
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier, Event, Thread, local
from urllib.error import HTTPError

import pytest

from griductive.game import controller as game_module
from griductive.game.engine import GameSession, load_puzzle
from griductive.models import Clue, SolverTimeout
from griductive.validation.uniqueness import check_unique_complete
from griductive.logic import encode_full_clues
from griductive.sat import solve
from griductive.web.controller import WebController
from griductive.web.session import SessionHost, StaleOperation
from griductive.web.server import create_server
from test_web_ui import _request

ROOT = Path(__file__).resolve().parents[1]
PUZZLES = ROOT / 'puzzles'


@pytest.fixture
def api(request):
    with create_server(port=0, puzzles_dir=PUZZLES, **getattr(request, 'param', {})) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(action, payload=None, method='POST'):
            return _request(f'http://127.0.0.1:{server.server_port}/api/{action}', method, payload)[1]
        yield request
        server.shutdown()
        thread.join()


@pytest.mark.parametrize('puzzle_id', ['tutorial_3x3', 'extensions_3x3', 'mixed_counting_4x4', 'case_5x5_a'])
def test_int01_int02_real_http_full_game(api, puzzle_id):
    initial = api('game/load', {'puzzle_id': puzzle_id})
    hint = api('game/hint', method='GET')
    assert hint['status'] == 'FOUND'
    assert api('game/state', method='GET') == initial
    manual = api('game/verdict', {'cell': hint['cell'], 'status': hint['suggested_verdict']})
    assert manual['outcome'] == 'ACCEPTED'
    result = api('game/auto-solve')
    assert result['terminal_status'] == 'SOLVED'
    assert result['state']['revealed_count'] == initial['total_count']
    assert len(result['state']['trace']) == initial['total_count'] - initial['revealed_count']
    active = {c['clue']['id'] for c in initial['cards'] if c['clue']}
    for step in result['state']['trace']:
        assert set(step['active_clues']) == active
        assert step['queries']
        assert any(q['purpose'] == 'VERDICT_RECHECK' for q in step['queries'])
        assert all('assignment' not in q for q in step['queries'])
        active.add(step['newly_revealed_clue'])
    assert api('game/restart') == initial


def test_int03_int04_public_privacy_and_rejected_manual(api):
    initial = api('game/load', {'puzzle_id': 'tutorial_3x3'})
    for cell, status, outcome in [('C1', 'INNOCENT', 'NOT_PROVABLE'), ('B1', 'CRIMINAL', 'CONTRADICTED')]:
        result = api('game/verdict', {'cell': cell, 'status': status})
        assert result['outcome'] == outcome
        assert result['state'] == initial
        assert result['proof']['active_clue_ids'] == ['c-A1']
        assert 'c-C1' not in json.dumps(result)
        assert 'hidden_status' not in json.dumps(result)
    for payload in [{'cell': 'Z9', 'status': 'INNOCENT'}, {'cell': 'A1', 'status': 'CRIMINAL'}, {'cell': 'B1', 'status': 'BAD'}]:
        with pytest.raises(HTTPError) as error:
            api('game/verdict', payload)
        assert error.value.code == 400
        assert api('game/state', method='GET') == initial


def test_real_web_path_covers_all_clues_regions_and_uniqueness():
    kinds, regions = set(), set()
    view = WebController(PUZZLES)
    for path in sorted(PUZZLES.glob('[345]x[345]/*.json')):
        puzzle = load_puzzle(str(path))
        assert check_unique_complete(puzzle, encode_full_clues, solve)
        view.load_puzzle(puzzle.id)
        assert view.auto_solve()['terminal_status'] == 'SOLVED'
        for card in puzzle.cards:
            kinds.add(card.clue.kind)
            if 'region' in card.clue.data:
                regions.add(card.clue.data['region']['type'])
    assert kinds == {'FACT', 'SAME', 'DIFFERENT', 'EXACTLY', 'AT_LEAST', 'AT_MOST', 'PARITY', 'COMPOUND'}
    assert regions == {'row', 'column', 'neighbors', 'cells'}


@pytest.mark.parametrize('puzzle_id,steps', [('ambiguous_3x3', 0), ('stuck_4x4', 3)])
def test_http_stuck_does_not_guess(api, puzzle_id, steps):
    initial = api('game/load', {'puzzle_id': puzzle_id})
    result = api('game/auto-solve')
    assert result['terminal_status'] == 'STUCK'
    assert len(result['steps_added']) == steps
    assert not result['state']['solved']
    stopped = result['state']
    assert api('game/hint', method='GET')['status'] == 'NONE'
    assert api('game/auto-solve')['state'] == stopped
    assert api('game/restart') == initial


def test_inconsistent_public_state_uses_real_pipeline_without_loading_false_puzzle(monkeypatch):
    # Public fault injection only: the production loader must still reject false puzzles.
    from griductive.game.engine import PuzzleValidationError
    with pytest.raises(PuzzleValidationError):
        load_puzzle(str(PUZZLES / 'negative/inconsistent_public_3x3.json'))
    view = WebController(PUZZLES)
    public = view._game.snapshot()
    contradictory = replace(public.cards[0], clue=Clue('public-fault', 'FACT', {'cell': 'A1', 'status': 'INNOCENT'}))
    public = replace(public, cards=(contradictory,) + public.cards[1:])
    monkeypatch.setattr(GameSession, 'snapshot', lambda self: public)
    assert view.get_hint()['status'] == 'INCONSISTENT'
    assert view.step()['outcome'] == 'INCONSISTENT'
    result = view.auto_solve()
    assert result['terminal_status'] == 'INCONSISTENT'
    assert result['steps_added'] == []
    assert result['state']['revealed_count'] == 1


@pytest.mark.parametrize('operation,args', [('get_hint', ()), ('step', ()), ('auto_solve', ()), ('submit_verdict', ('B1', 'INNOCENT'))])
def test_real_solver_timeout_never_becomes_unsat(operation, args):
    host = SessionHost(WebController(PUZZLES, solve_timeout_s=0.0))
    before = host.execute('get_public_state_dict')
    with pytest.raises(SolverTimeout):
        host.execute(operation, *args)
    assert host.execute('get_public_state_dict') == before


@pytest.mark.parametrize('reset,args', [('restart', ()), ('load_puzzle', ('mixed_counting_4x4',))])
@pytest.mark.parametrize('operation', ['auto_solve', 'get_hint', 'step'])
def test_reset_invalidates_inflight_real_work(monkeypatch, reset, args, operation):
    host = SessionHost(WebController(PUZZLES))
    started, release = Event(), Event()
    real_solve = game_module.solve
    def held_solver(*solver_args, **kwargs):
        started.set()
        assert release.wait(5)
        return real_solve(*solver_args, **kwargs)
    monkeypatch.setattr(game_module, 'solve', held_solver)
    with ThreadPoolExecutor(max_workers=1) as workers:
        job = workers.submit(host.execute, operation)
        try:
            assert started.wait(5)
            new_state = host.execute(reset, *args)
        finally:
            release.set()
        with pytest.raises(StaleOperation):
            job.result(timeout=5)
    assert host.execute('get_public_state_dict') == new_state
    assert new_state['trace'] == []


def test_timeout_after_partial_work_does_not_publish_reveals(monkeypatch):
    host = SessionHost(WebController(PUZZLES))
    initial = host.execute('get_public_state_dict')
    real_submit = GameSession.submit_verdict
    did_reveal = False
    real_solve = game_module.solve
    def submit(self, *args):
        nonlocal did_reveal
        result = real_submit(self, *args)
        did_reveal = True
        return result
    def interrupted(*args, **kwargs):
        if did_reveal:
            raise SolverTimeout('injected interruption after a real reveal')
        return real_solve(*args, **kwargs)
    monkeypatch.setattr(GameSession, 'submit_verdict', submit)
    monkeypatch.setattr(game_module, 'solve', interrupted)
    with pytest.raises(SolverTimeout):
        host.execute('auto_solve')
    assert did_reveal
    assert host.execute('get_public_state_dict') == initial


@pytest.mark.parametrize('api', [{'solve_timeout_s': 0.0}], indirect=True)
@pytest.mark.parametrize('action,method,payload', [
    ('hint', 'GET', None), ('step', 'POST', None), ('auto-solve', 'POST', None),
    ('verdict', 'POST', {'cell': 'B1', 'status': 'INNOCENT'}),
])
def test_http_timeout_has_explicit_status_and_keeps_state(api, action, method, payload):
    before = api('game/state', method='GET')
    with pytest.raises(HTTPError) as error:
        api('game/' + action, payload, method)
    assert error.value.code == 504
    assert json.load(error.value)['code'] == 'TIMEOUT'
    assert api('game/state', method='GET') == before


@pytest.mark.parametrize('reset,payload', [('restart', None), ('load', {'puzzle_id': 'mixed_counting_4x4'}), ('load', {'puzzle_id': 'missing'})])
def test_http_reset_during_solve_discards_old_result(api, monkeypatch, reset, payload):
    started, release = Event(), Event()
    real_solve = game_module.solve
    def held(*args, **kwargs):
        started.set()
        assert release.wait(5)
        return real_solve(*args, **kwargs)
    monkeypatch.setattr(game_module, 'solve', held)
    with ThreadPoolExecutor(max_workers=1) as workers:
        job = workers.submit(api, 'game/auto-solve')
        try:
            assert started.wait(5)
            if payload and payload['puzzle_id'] == 'missing':
                with pytest.raises(HTTPError) as error:
                    api('game/' + reset, payload)
                assert error.value.code == 404
                new_state = api('game/state', method='GET')
            else:
                new_state = api('game/' + reset, payload)
        finally:
            release.set()
        with pytest.raises(HTTPError) as error:
            job.result(timeout=5)
        assert error.value.code == 409
        assert json.load(error.value)['code'] == 'STALE_RESULT'
    assert api('game/state', method='GET') == new_state
    assert new_state['trace'] == []


def test_bad_data_load_is_transactional_and_does_not_disclose_hidden(tmp_path):
    raw = json.loads((PUZZLES / '3x3/tutorial_3x3.json').read_text(encoding='utf-8'))
    (tmp_path / 'tutorial.json').write_text(json.dumps(raw), encoding='utf-8')
    raw['id'] = 'broken'
    raw['cards'][0]['clue']['status'] = 'CRIMINAL'
    (tmp_path / 'broken.json').write_text(json.dumps(raw), encoding='utf-8')
    host = SessionHost(WebController(tmp_path))
    before = host.execute('get_public_state_dict')
    with pytest.raises(ValueError, match='^Puzzle failed validation$'):
        host.execute('load_puzzle', 'broken')
    assert host.execute('get_public_state_dict') == before


def test_competing_proofs_cannot_both_commit_the_same_revision(monkeypatch):
    host = SessionHost(WebController(PUZZLES))
    barrier, seen = Barrier(2), local()
    real_solve = game_module.solve
    def together(*args, **kwargs):
        if not getattr(seen, 'started', False):
            seen.started = True
            barrier.wait(timeout=5)
        return real_solve(*args, **kwargs)
    monkeypatch.setattr(game_module, 'solve', together)
    with ThreadPoolExecutor(max_workers=2) as workers:
        jobs = [workers.submit(host.execute, 'step') for _ in range(2)]
        outcomes = []
        for job in jobs:
            try:
                outcomes.append(job.result(timeout=5)['outcome'])
            except StaleOperation:
                outcomes.append('STALE_RESULT')
    assert sorted(outcomes) == ['ACCEPTED', 'STALE_RESULT']
    assert host.execute('get_public_state_dict')['revealed_count'] == 2
