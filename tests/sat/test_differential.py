"""Randomized differential testing and edge case suite for Task 3.3.

Test IDs: SATT-01, SATT-02, SATT-03, SATT-04.
Cross-checks production DPLL against `exhaustive_oracle.py` across 100+ formulas.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Sequence

import pytest
from griductive.models import CNF
from griductive.sat import solve

# Ensure tests/sat can import sibling test helpers
sys.path.insert(0, str(Path(__file__).resolve().parent))
from exhaustive_oracle import exhaustive_sat, validate_sat_model

FIXED_TEST_SEED = 20261118


def _generate_random_cnf(
    rng: random.Random,
    max_vars: int = 8,
    max_clauses: int = 18,
    max_clause_len: int = 4,
) -> CNF:
    """Generate a random CNF formula with deterministic variable bounds."""
    n_vars = rng.randint(1, max_vars)
    n_clauses = rng.randint(0, max_clauses)
    clauses: list[tuple[int, ...]] = []

    for _ in range(n_clauses):
        clause_len = rng.randint(0, min(max_clause_len, n_vars))
        if clause_len == 0:
            # Occasionally generate empty clause to test immediate conflict
            clauses.append(())
            continue
        vars_in_clause = rng.sample(range(1, n_vars + 1), clause_len)
        clause = tuple(rng.choice([-1, 1]) * v for v in vars_in_clause)
        clauses.append(clause)

    return CNF(
        clauses=tuple(clauses),
        primary_count=n_vars,
        variable_count=n_vars,
    )


def _generate_random_assumptions(
    rng: random.Random,
    var_count: int,
    max_assumptions: int = 3,
) -> tuple[int, ...]:
    """Generate random non-conflicting or occasionally conflicting assumptions."""
    count = rng.randint(0, min(max_assumptions, var_count))
    if count == 0:
        return ()
    chosen_vars = rng.sample(range(1, var_count + 1), count)
    return tuple(rng.choice([-1, 1]) * v for v in chosen_vars)


# =====================================================================
# Acceptance Tests: SATT-01 .. SATT-04
# =====================================================================


def test_satt01_differential_100_random_cnfs():
    """SATT-01: 100 random CNFs (<=8 variables) cross-checked against exhaustive oracle."""
    rng = random.Random(FIXED_TEST_SEED)
    sat_count = 0
    unsat_count = 0

    for i in range(100):
        cnf = _generate_random_cnf(rng, max_vars=8, max_clauses=16, max_clause_len=4)
        oracle_sat, oracle_model = exhaustive_sat(cnf)
        dpll_res = solve(cnf)

        assert dpll_res.is_sat == oracle_sat, (
            f"Case #{i} discrepancy: DPLL returned is_sat={dpll_res.is_sat}, "
            f"oracle returned is_sat={oracle_sat} for CNF: {cnf}"
        )

        if dpll_res.is_sat:
            sat_count += 1
            validate_sat_model(cnf, dpll_res.assignment)
        else:
            unsat_count += 1

    # Ensure our random suite covered both SAT and UNSAT cases meaningfully
    assert sat_count >= 15, f"Expected at least 15 SAT cases, got {sat_count}"
    assert unsat_count >= 15, f"Expected at least 15 UNSAT cases, got {unsat_count}"


def test_satt02_model_validation_on_all_sat_cases():
    """SATT-02: Every SAT assignment strictly satisfies all clauses and assumptions."""
    rng = random.Random(FIXED_TEST_SEED + 1)

    for i in range(50):
        cnf = _generate_random_cnf(rng, max_vars=7, max_clauses=12, max_clause_len=3)
        assumptions = _generate_random_assumptions(rng, cnf.variable_count, max_assumptions=2)

        oracle_sat, _ = exhaustive_sat(cnf, assumptions=assumptions)
        res = solve(cnf, assumptions=assumptions)

        assert res.is_sat == oracle_sat, f"Assumption case #{i} discrepancy"
        if res.is_sat:
            validate_sat_model(cnf, res.assignment, assumptions=assumptions)


def test_satt03_edge_cases_and_anomalies():
    """SATT-03: Repeated literals, tautologies, negative literals, and disconnected variables."""
    # 1. Repeated literals in clauses
    cnf_repeated = CNF(
        clauses=((1, 1, 2), (-1, -1, 2), (2, 2)),
        primary_count=2,
        variable_count=2,
    )
    res_rep = solve(cnf_repeated)
    assert res_rep.is_sat is True
    assert res_rep.assignment[2] is True
    validate_sat_model(cnf_repeated, res_rep.assignment)

    # 2. Tautology clauses: (1, -1) should not break resolution or branching
    cnf_taut = CNF(
        clauses=((1, -1), (2, -2, 3), (-3,)),
        primary_count=3,
        variable_count=3,
    )
    res_taut = solve(cnf_taut)
    assert res_taut.is_sat is True
    assert res_taut.assignment[3] is False
    validate_sat_model(cnf_taut, res_taut.assignment)

    # 3. All negative literals
    cnf_neg = CNF(
        clauses=((-1, -2), (-2, -3), (-1, -3)),
        primary_count=3,
        variable_count=3,
    )
    res_neg = solve(cnf_neg)
    assert res_neg.is_sat is True
    validate_sat_model(cnf_neg, res_neg.assignment)

    # 4. Disconnected variables (e.g. 5 variables, but only var 1 in clauses)
    cnf_disc = CNF(
        clauses=((1,),),
        primary_count=2,
        variable_count=5,
    )
    res_disc = solve(cnf_disc)
    assert res_disc.is_sat is True
    assert set(res_disc.assignment.keys()) == {1, 2, 3, 4, 5}
    assert res_disc.assignment[1] is True
    validate_sat_model(cnf_disc, res_disc.assignment)

    # 5. Full 3-variable UNSAT pigeonhole / contradiction
    cnf_all_excluded = CNF(
        clauses=(
            (1, 2), (1, -2), (-1, 2), (-1, -2)
        ),
        primary_count=2,
        variable_count=2,
    )
    res_ex = solve(cnf_all_excluded)
    assert res_ex.is_sat is False
    assert res_ex.assignment is None


def test_satt04_deterministic_run_and_branching_stability():
    """SATT-04: Running identical inputs yields strictly identical outputs and counters."""
    rng1 = random.Random(FIXED_TEST_SEED + 99)
    rng2 = random.Random(FIXED_TEST_SEED + 99)

    for i in range(30):
        cnf1 = _generate_random_cnf(rng1, max_vars=6, max_clauses=10, max_clause_len=3)
        cnf2 = _generate_random_cnf(rng2, max_vars=6, max_clauses=10, max_clause_len=3)

        res1 = solve(cnf1)
        res2 = solve(cnf2)

        assert res1.is_sat == res2.is_sat, f"Run {i}: is_sat differed"
        assert res1.assignment == res2.assignment, f"Run {i}: assignment differed"
        assert res1.stats.decisions == res2.stats.decisions, f"Run {i}: decisions differed"
        assert res1.stats.propagations == res2.stats.propagations, f"Run {i}: propagations differed"
        assert res1.stats.backtracks == res2.stats.backtracks, f"Run {i}: backtracks differed"
