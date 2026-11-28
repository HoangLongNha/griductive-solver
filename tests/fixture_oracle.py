"""Independent exhaustive oracle FOR TEST FIXTURES ONLY (not production SAT)."""
from itertools import product

from griductive.logic.regions import resolve_region
from griductive.logic.semantics import evaluate_clue
from griductive.models import Clue


def ids(n):
    return [f"{chr(65+c)}{r}" for r in range(1,n+1) for c in range(n)]

def region_cells(region,n):
    return list(resolve_region(region, n))

def evaluate(c,a,n):
    model_clue = Clue(
        c.get('id', 'c'),
        c['kind'],
        {k: v for k, v in c.items() if k not in ('id', 'kind')},
    )
    return evaluate_clue(model_clue, a, n)

def models(p, revealed):
    cards={c['cell']:c for c in p['cards']};keys=ids(p['size'])
    for bits in product((False,True),repeat=len(keys)):
        assignment=dict(zip(keys,bits))
        if any(assignment[k] != (cards[k]['hidden_status']=='CRIMINAL') for k in revealed):continue
        if all(evaluate(cards[k]['clue'],assignment,p['size']) for k in revealed):
            yield assignment

def forced(p,shown):
    ms=list(models(p,shown))
    if not ms:return 'INCONSISTENT',None
    for k in ids(p['size']):
        if k in shown:continue
        vals={m[k] for m in ms}
        if len(vals)==1:return k, vals.pop()
    return None,None

def no_guess_walk(p):
    shown=set(p['initial_revealed']);steps=[]
    while len(shown)<p['size']**2:
        cell,value=forced(p,shown)
        if cell in (None,'INCONSISTENT'):return cell,steps
        actual={c['cell']:(c['hidden_status']=='CRIMINAL') for c in p['cards']}
        assert actual[cell]==value,(p['id'],cell,value)
        shown.add(cell);steps.append(cell)
    return 'SOLVED',steps


def full_clue_models(p):
    """Enumerate models of ALL clues without unit verdicts; fixture-only oracle."""
    keys=ids(p['size'])
    for bits in product((False,True),repeat=len(keys)):
        a=dict(zip(keys,bits))
        if all(evaluate(c['clue'],a,p['size']) for c in p['cards']):
            yield a
