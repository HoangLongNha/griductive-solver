"""Cardinality constraints over literals as CNF (task 2.2).

Small constraints use the direct combinatorial encoding without auxiliary
variables (the canonical choice for rows, columns and neighborhoods):

- AT_MOST k:  for every (k+1)-subset S, add  OR(-x for x in S);
- AT_LEAST k: for every (n-k+1)-subset S, add OR(x for x in S);
- EXACTLY k:  both.

When the direct encoding would exceed `DIRECT_CLAUSE_LIMIT` clauses (e.g. a
large explicit region on a 5x5 board) the Sinz sequential counter is used
instead; its auxiliary variables come from an `AuxPool` in allocation order.
"""
from itertools import combinations
from math import comb

from griductive.models import Clause

DIRECT_CLAUSE_LIMIT = 256


class AuxPool:
    """Allocates auxiliary variable IDs primary_count+1, +2, ... deterministically."""

    def __init__(self, primary_count: int):
        self.primary_count = primary_count
        self.top = primary_count

    def new(self) -> int:
        self.top += 1
        return self.top

    @property
    def aux_count(self) -> int:
        return self.top - self.primary_count


def at_most(lits: tuple[int, ...], k: int, pool: AuxPool,
            direct_limit: int = DIRECT_CLAUSE_LIMIT) -> list[Clause]:
    """At most k of the (distinct-variable) literals are true."""
    n = len(lits)
    if k < 0:
        raise ValueError('k must be non-negative')
    if k >= n:
        return []
    if comb(n, k + 1) <= direct_limit:
        return [tuple(-lit for lit in subset) for subset in combinations(lits, k + 1)]
    return _sequential_at_most(lits, k, pool)


def at_least(lits: tuple[int, ...], k: int, pool: AuxPool,
             direct_limit: int = DIRECT_CLAUSE_LIMIT) -> list[Clause]:
    """At least k true  <=>  at most n-k of the negated literals are true."""
    if not 0 <= k <= len(lits):
        raise ValueError('k must be in 0..len(lits)')
    return at_most(tuple(-lit for lit in lits), len(lits) - k, pool, direct_limit)


def exactly(lits: tuple[int, ...], k: int, pool: AuxPool,
            direct_limit: int = DIRECT_CLAUSE_LIMIT) -> list[Clause]:
    return at_most(lits, k, pool, direct_limit) + at_least(lits, k, pool, direct_limit)


def _sequential_at_most(lits, k, pool):
    """Sinz (2005) sequential counter.

    The clauses force s[i][j] = True whenever at least j+1 of lits[0..i] are
    true; the converse is not enforced, so s[i][j] cannot be read back as an
    exact count. Any assignment with at most k true literals extends to a model.
    """
    if k == 0:
        return [(-lit,) for lit in lits]
    n = len(lits)
    s = [[pool.new() for _ in range(k)] for _ in range(n - 1)]
    clauses = [(-lits[0], s[0][0])]
    clauses += [(-s[0][j],) for j in range(1, k)]
    for i in range(1, n - 1):
        clauses.append((-lits[i], s[i][0]))
        clauses.append((-s[i - 1][0], s[i][0]))
        for j in range(1, k):
            clauses.append((-lits[i], -s[i - 1][j - 1], s[i][j]))
            clauses.append((-s[i - 1][j], s[i][j]))
        clauses.append((-lits[i], -s[i - 1][k - 1]))
    clauses.append((-lits[n - 1], -s[n - 2][k - 1]))
    return clauses
