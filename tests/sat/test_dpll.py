"""Unit and acceptance tests for Task 3.1: DPLL core.

Test IDs: SAT-01, SAT-02, SAT-03, SAT-04, SAT-05.
Plus preliminary coverage for STAT-01..STAT-04 (assumptions & immutability).
"""
import pytest
from griductive.models import CNF, SATResult, SATStats, SolverTimeout
from griductive.sat.dpll import solve


def _validate_satisfying_model(cnf: CNF, assignment: dict[int, bool] | None, assumptions: tuple[int, ...] = ()) -> None:
    """Helper to verify that a SAT assignment is complete and satisfies all clauses and assumptions."""
    assert assignment is not None, "SAT result must provide an assignment dict"
    expected_vars = set(range(1, cnf.variable_count + 1))
    assert set(assignment.keys()) == expected_vars, (
        f"Assignment keys {set(assignment.keys())} != expected 1..{cnf.variable_count}"
    )

    # Verify assumptions are satisfied
    for lit in assumptions:
        var = abs(lit)
        expected_val = lit > 0
        assert assignment[var] == expected_val, f"Assignment violates assumption {lit}"

    # Verify all clauses are satisfied
    for clause in cnf.clauses:
        assert any(
            (assignment[abs(lit)] if lit > 0 else not assignment[abs(lit)])
            for lit in clause
        ), f"Assignment {assignment} violates clause {clause}"


# =====================================================================
# Acceptance Tests: SAT-01 .. SAT-05
# =====================================================================


def test_sat01_simple_implication():
    """SAT-01: CNF [[1,2], [-1,2]] -> SAT and model has var 2 (B) = True."""
    cnf = CNF(clauses=((1, 2), (-1, 2)), primary_count=2, variable_count=2)
    res = solve(cnf)

    assert res.is_sat is True
    assert res.assignment is not None
    assert res.assignment[2] is True
    _validate_satisfying_model(cnf, res.assignment)
    assert res.stats.decisions >= 0
    assert res.stats.propagations >= 1
    assert res.stats.runtime_s >= 0.0


def test_sat02_direct_contradiction():
    """SAT-02: CNF [[1], [-1]] -> UNSAT."""
    cnf = CNF(clauses=((1,), (-1,)), primary_count=1, variable_count=1)
    res = solve(cnf)

    assert res.is_sat is False
    assert res.assignment is None
    assert res.stats.decisions == 0
    assert res.stats.propagations >= 1
    assert res.stats.runtime_s >= 0.0


def test_sat03_empty_cases():
    """SAT-03: Empty clause -> UNSAT; empty conjunction -> SAT."""
    # Empty clause inside CNF
    empty_clause_cnf = CNF(clauses=((),), primary_count=1, variable_count=1)
    res_empty_clause = solve(empty_clause_cnf)
    assert res_empty_clause.is_sat is False
    assert res_empty_clause.assignment is None

    # Empty clause among other clauses
    mixed_empty_clause_cnf = CNF(clauses=((1, 2), ()), primary_count=2, variable_count=2)
    res_mixed = solve(mixed_empty_clause_cnf)
    assert res_mixed.is_sat is False
    assert res_mixed.assignment is None

    # Empty conjunction (no clauses)
    empty_cnf = CNF(clauses=(), primary_count=3, variable_count=3)
    res_empty = solve(empty_cnf)
    assert res_empty.is_sat is True
    _validate_satisfying_model(empty_cnf, res_empty.assignment)

    # Zero-variable empty conjunction
    zero_var_cnf = CNF(clauses=(), primary_count=0, variable_count=0)
    res_zero = solve(zero_var_cnf)
    assert res_zero.is_sat is True
    assert res_zero.assignment == {}


def test_sat04_deterministic_smallest_variable_selection():
    """SAT-04: Deterministic selection of smallest unassigned variable."""
    # Under multiple unconstrained variables, runs must return identical models and stats
    cnf = CNF(clauses=((1, 2, 3), (-1, 2)), primary_count=3, variable_count=3)
    res1 = solve(cnf)
    res2 = solve(cnf)

    assert res1.is_sat is True
    assert res2.is_sat is True
    assert res1.assignment == res2.assignment
    assert res1.stats.decisions == res2.stats.decisions
    assert res1.stats.propagations == res2.stats.propagations
    assert res1.stats.backtracks == res2.stats.backtracks
    _validate_satisfying_model(cnf, res1.assignment)


def test_sat05_backtracking_and_refutation():
    """SAT-05: Case requiring branch failure and backtracking to find SAT or prove UNSAT."""
    # SAT case where True branch on 1 fails, forcing backtrack to 1=False:
    # If 1=True: (-1, 2) forces 2=True, but (-1, -2) conflicts!
    # So 1 must be False, which satisfies (-1, 2) and (-1, -2); (1, 2) forces 2=True.
    sat_cnf = CNF(clauses=((-1, 2), (-1, -2), (1, 2)), primary_count=2, variable_count=2)
    res_sat = solve(sat_cnf)
    assert res_sat.is_sat is True
    assert res_sat.assignment == {1: False, 2: True}
    assert res_sat.stats.decisions >= 1
    assert res_sat.stats.backtracks >= 1
    _validate_satisfying_model(sat_cnf, res_sat.assignment)

    # UNSAT case where both branches fail:
    # 2 variables, all 4 combinations excluded
    unsat_cnf = CNF(
        clauses=((-1, 2), (-1, -2), (1, 2), (1, -2)),
        primary_count=2,
        variable_count=2,
    )
    res_unsat = solve(unsat_cnf)
    assert res_unsat.is_sat is False
    assert res_unsat.assignment is None
    assert res_unsat.stats.decisions >= 1
    assert res_unsat.stats.backtracks >= 2


# =====================================================================
# Additional invariants and contract compliance tests
# =====================================================================


def test_complete_model_with_free_auxiliary_variables():
    """Contract: assignment must be COMPLETE (1..variable_count), even for unconstrained aux variables."""
    cnf = CNF(clauses=((1,),), primary_count=1, variable_count=4)
    res = solve(cnf)

    assert res.is_sat is True
    assert res.assignment is not None
    assert set(res.assignment.keys()) == {1, 2, 3, 4}
    assert res.assignment[1] is True
    _validate_satisfying_model(cnf, res.assignment)


def test_assumptions_without_mutating_input_cnf():
    """STAT-01 & STAT-03: Assumptions supported, input CNF remains completely unmodified."""
    cnf = CNF(clauses=((-1,),), primary_count=1, variable_count=1)
    original_clauses = cnf.clauses

    # Assumption +1 contradicts KB's -1
    res = solve(cnf, assumptions=(1,))
    assert res.is_sat is False
    assert cnf.clauses is original_clauses
    assert cnf.clauses == ((-1,),)


def test_contradictory_assumptions():
    """STAT-02: Simultaneous assumptions (+1, -1) immediately return UNSAT."""
    cnf = CNF(clauses=((1, 2),), primary_count=2, variable_count=2)
    res = solve(cnf, assumptions=(1, -1))
    assert res.is_sat is False
    assert res.assignment is None


def test_tautology_and_duplicate_literals():
    """Robustness against duplicate literals and tautologies in clauses."""
    # (1, 1, 2) has duplicate 1; (2, -2, 1) is a tautology
    cnf = CNF(clauses=((1, 1, 2), (2, -2, 1)), primary_count=2, variable_count=2)
    res = solve(cnf)
    assert res.is_sat is True
    _validate_satisfying_model(cnf, res.assignment)


def test_timeout_support():
    """SolverTimeout raised when time limit is exceeded."""
    # Create a 20-variable pigeonhole-like UNSAT problem with tiny timeout
    clauses = []
    for i in range(1, 15):
        for j in range(i + 1, 16):
            clauses.append((-i, -j))
    cnf = CNF(clauses=tuple(clauses), primary_count=15, variable_count=15)
    # With a timeout of 0.000001s, it should trigger timeout
    with pytest.raises(SolverTimeout):
        solve(cnf, timeout_s=0.000001)


def test_input_validation():
    """Invalid literals and bounds raise ValueError or TypeError."""
    with pytest.raises(TypeError):
        solve("not a cnf")  # type: ignore

    with pytest.raises(ValueError):
        # Literal 0 is invalid
        solve(CNF(clauses=((0,),), primary_count=1, variable_count=1))

    with pytest.raises(ValueError):
        # Literal 3 exceeds variable_count 2
        solve(CNF(clauses=((3,),), primary_count=2, variable_count=2))

    with pytest.raises(ValueError):
        # Assumption 5 exceeds variable_count 2
        solve(CNF(clauses=((1,),), primary_count=2, variable_count=2), assumptions=(5,))
