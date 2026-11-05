import json
from pathlib import Path
import pytest
from fixture_oracle import evaluate, ids, models, full_clue_models, no_guess_walk

ROOT=Path(__file__).resolve().parents[1]
GOOD=sorted((ROOT/'puzzles'/'3x3').glob('*.json'))+sorted((ROOT/'puzzles'/'4x4').glob('*.json'))

@pytest.mark.parametrize('file',GOOD,ids=lambda f:f.stem)
def test_valid_fixture_is_true_unique_and_solvable(file):
    p=json.loads(file.read_text(encoding='utf-8'))
    keys=ids(p['size'])
    assert sorted(c['cell'] for c in p['cards'])==sorted(keys)
    assert len({c['name'] for c in p['cards']})==len(keys)
    a={c['cell']:(c['hidden_status']=='CRIMINAL') for c in p['cards']}
    assert all(evaluate(c['clue'],a,p['size']) for c in p['cards'])
    assert len(list(full_clue_models(p)))==1
    outcome,trace=no_guess_walk(p)
    assert outcome=='SOLVED'
    assert len(trace)==len(keys)-len(p['initial_revealed'])

def test_ambiguous_fixture_has_no_next_proof():
    p=json.loads((ROOT/'puzzles/negative/ambiguous_3x3.json').read_text())
    outcome,trace=no_guess_walk(p)
    assert outcome is None and not trace

def test_inconsistent_public_fixture_is_rejected():
    p=json.loads((ROOT/'puzzles/negative/inconsistent_public_3x3.json').read_text())
    assert list(models(p,set(p['initial_revealed'])))==[]
