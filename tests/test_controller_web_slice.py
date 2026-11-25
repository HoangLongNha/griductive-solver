import json
from pathlib import Path
from threading import Thread

from griductive.web.server import create_server
from griductive.web.controller import WebController

from test_web_ui import _request


def test_diagnostic_puzzles_are_selectable_and_reach_stuck():
    root = Path(__file__).resolve().parents[1]
    controller = WebController(root / 'puzzles')
    diagnostics = {p['id'] for p in controller.list_puzzles() if p['category'] == 'diagnostic'}
    assert diagnostics == {'ambiguous_3x3', 'stuck_4x4'}
    for puzzle_id, steps in [('ambiguous_3x3', 0), ('stuck_4x4', 3)]:
        controller.load_puzzle(puzzle_id)
        result = controller.auto_solve()
        assert result['terminal_status'] == 'STUCK'
        assert len(result['steps_added']) == steps


def test_completed_step_keeps_ledger_without_reusing_previous_proof():
    root = Path(__file__).resolve().parents[1]
    controller = WebController(root / 'puzzles')
    controller.load_puzzle('tutorial_3x3')
    for _ in range(8):
        assert controller.step()['outcome'] == 'ACCEPTED'
    solved = controller.get_public_state_dict()
    assert solved['solved']
    assert len(solved['trace']) == 8
    for _ in range(2):
        result = controller.step()
        assert result['outcome'] == 'NOT_PROVABLE'
        assert result['message'] == 'Puzzle already solved'
        assert result['newly_revealed'] is None
        assert result['proof'] is None
        assert result['state'] == controller.get_public_state_dict() == solved


def test_react_api_runs_real_one_move_and_preserves_rejected_state():
    root = Path(__file__).resolve().parents[1]
    with create_server(port=0, puzzles_dir=root / 'puzzles', web_dir=root / 'web') as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'

        def post(action, payload=None):
            return _request(f'{base}/api/game/{action}', 'POST', payload or {})[1]

        try:
            initial = post('load', {'puzzle_id': 'tutorial_3x3'})
            assert [c['cell'] for c in initial['cards'] if c['revealed']] == ['A1']
            for cell, status, outcome in (
                ('C1', 'INNOCENT', 'NOT_PROVABLE'), ('B1', 'CRIMINAL', 'CONTRADICTED'),
            ):
                rejected = post('verdict', {'cell': cell, 'status': status})
                assert rejected['outcome'] == outcome
                assert rejected['state'] == initial
                assert rejected['proof']['cnf']['clauses'] == [[1], [-2]]

            accepted = post('step')
            assert accepted['outcome'] == 'ACCEPTED'
            assert accepted['newly_revealed'] == 'B1'
            assert [c['cell'] for c in accepted['state']['cards'] if c['revealed']] == ['A1', 'B1']
            b1, c1 = accepted['state']['cards'][1:3]
            assert b1['known_status'] == 'INNOCENT' and b1['clue']['id'] == 'c-B1'
            assert c1['known_status'] is None and c1['clue'] is None
            assert accepted['proof']['active_clue_ids'] == ['c-A1']
            assert accepted['proof']['cnf']['clauses'] == [[1], [-2]]
            assert any(q['assumptions'] == [2] and not q['is_sat'] for q in accepted['proof']['queries'])
            assert 'c-C1' not in json.dumps(accepted)
            assert post('restart') == initial
        finally:
            server.shutdown()
            thread.join()
