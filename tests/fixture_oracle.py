"""Independent exhaustive oracle FOR TEST FIXTURES ONLY (not production SAT)."""
from itertools import product

def ids(n):
    return [f"{chr(65+c)}{r}" for r in range(1,n+1) for c in range(n)]

def region_cells(region,n):
    kind=region['type']
    if kind=='row': return [f"{chr(65+c)}{region['index']}" for c in range(n)]
    if kind=='column': return [f"{region['index']}{r}" for r in range(1,n+1)]
    if kind=='cells': return region['cells']
    center=region['cell']; cx=ord(center[0])-65;cy=int(center[1:])-1
    return [f"{chr(65+x)}{y+1}" for y in range(n) for x in range(n) if max(abs(x-cx),abs(y-cy))==1]

def evaluate(c,a,n):
    k=c['kind']
    if k=='FACT': return a[c['cell']] == (c['status']=='CRIMINAL')
    if k=='SAME': return a[c['cells'][0]]==a[c['cells'][1]]
    if k=='DIFFERENT': return a[c['cells'][0]]!=a[c['cells'][1]]
    if k=='COMPOUND':
        prem=all(a[x['cell']]==(x['status']=='CRIMINAL') for x in c['premises'])
        concl=a[c['conclusion']['cell']]==(c['conclusion']['status']=='CRIMINAL')
        return not prem or concl
    val=sum(a[x] for x in region_cells(c['region'],n))
    if k=='EXACTLY': return val==c['k']
    if k=='AT_LEAST': return val>=c['k']
    if k=='AT_MOST': return val<=c['k']
    if k=='PARITY': return (val%2==0)==(c['parity']=='EVEN')
    raise ValueError(k)

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
