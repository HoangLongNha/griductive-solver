"""Test-only CNF checks (NOT the production SAT solver; that is VT3's DPLL).

`has_extension` decides whether fixed primary values extend to a model by
propagation plus naive branching over the remaining (auxiliary) variables.
"""
from itertools import product

from griductive.logic.semantics import evaluate_clue, referenced_cells
from griductive.models import cell_to_var, var_to_cell


def satisfies(clauses, assignment):
    return all(any(assignment[abs(lit)] == (lit > 0) for lit in clause) for clause in clauses)


def has_extension(clauses, fixed):
    assign = dict(fixed)
    while True:
        unit = None
        for clause in clauses:
            if any(assign.get(abs(lit)) == (lit > 0) for lit in clause):
                continue
            free = [lit for lit in clause if abs(lit) not in assign]
            if not free:
                return False
            if len(free) == 1:
                unit = free[0]
                break
        if unit is None:
            break
        assign[abs(unit)] = unit > 0
    for clause in clauses:
        if not any(assign.get(abs(lit)) == (lit > 0) for lit in clause):
            var = next(abs(lit) for lit in clause if abs(lit) not in assign)
            return (has_extension(clauses, {**assign, var: True})
                    or has_extension(clauses, {**assign, var: False}))
    return True


def classify(cnf, var):
    """Entailment by definition: KB |= C iff KB AND -C is UNSAT (test-only)."""
    clauses = list(cnf.clauses)
    if not has_extension(clauses, {}):
        return 'INCONSISTENT'
    if not has_extension(clauses + [(-var,)], {}):
        return 'CRIMINAL'
    if not has_extension(clauses + [(var,)], {}):
        return 'INNOCENT'
    return 'UNKNOWN'


def assert_clue_equivalent(clue, size, cnf_clauses, primary_count):
    """For every assignment of the referenced cells (others innocent):
    evaluator is true  <=>  some auxiliary completion satisfies the CNF."""
    cells = referenced_cells(clue, size)
    for bits in product((False, True), repeat=len(cells)):
        board = {var_to_cell(v, size): False for v in range(1, primary_count + 1)}
        board.update(zip(cells, bits))
        fixed = {cell_to_var(cell, size): value for cell, value in board.items()}
        expected = evaluate_clue(clue, board, size)
        assert has_extension(cnf_clauses, fixed) == expected, (clue, board)


def assert_lits_equivalent(clauses, n, predicate):
    """Literals 1..n: predicate(count, bits) <=> the clauses extend to a model."""
    for bits in product((False, True), repeat=n):
        fixed = dict(zip(range(1, n + 1), bits))
        assert has_extension(clauses, fixed) == predicate(bits), (n, bits)
