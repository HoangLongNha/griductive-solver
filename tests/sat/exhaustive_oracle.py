"""Exhaustive brute-force SAT oracle for differential testing (task 3.3).

This oracle is strictly test-only and explores all 2^n truth assignments
for small formulas (<= 16 variables). It is NEVER used in production code.
"""
from __future__ import annotations

from itertools import product
from typing import Sequence

from griductive.models import CNF


def exhaustive_sat(
    cnf: CNF,
    assumptions: Sequence[int] = (),
) -> tuple[bool, dict[int, bool] | None]:
    """Test-only exhaustive brute-force solver exploring all 2^n boolean assignments.

    Args:
        cnf: CNF formula with variable_count <= 16.
        assumptions: Optional unit literals that must be satisfied.

    Returns:
        tuple[bool, dict[int, bool] | None]: (True, satisfying_assignment) or (False, None).
    """
    n = cnf.variable_count
    if n > 16:
        raise ValueError(f"Exhaustive oracle restricted to <=16 variables, got {n}")

    # Check empty clause
    for clause in cnf.clauses:
        if len(clause) == 0:
            return False, None

    # Check conflicting assumptions
    assumptions_dict: dict[int, bool] = {}
    for lit in assumptions:
        v = abs(lit)
        val = lit > 0
        if v in assumptions_dict and assumptions_dict[v] != val:
            return False, None
        assumptions_dict[v] = val

    # Test all 2^n truth assignments
    for bits in product((False, True), repeat=n):
        assignment = {v: bits[v - 1] for v in range(1, n + 1)}

        # Check assumptions
        if any(assignment[v] != val for v, val in assumptions_dict.items()):
            continue

        # Check all clauses
        all_clauses_sat = True
        for clause in cnf.clauses:
            if not any(
                (assignment[abs(lit)] if lit > 0 else not assignment[abs(lit)])
                for lit in clause
            ):
                all_clauses_sat = False
                break

        if all_clauses_sat:
            return True, assignment

    return False, None


def validate_sat_model(
    cnf: CNF,
    assignment: dict[int, bool] | None,
    assumptions: Sequence[int] = (),
) -> None:
    """Strictly assert that a SAT assignment is complete and satisfies all clauses and assumptions."""
    assert assignment is not None, "SAT model cannot be None"
    expected_vars = set(range(1, cnf.variable_count + 1))
    actual_vars = set(assignment.keys())
    assert actual_vars == expected_vars, (
        f"Model missing variables or has extra variables. Expected {expected_vars}, got {actual_vars}"
    )

    # Check assumptions
    for lit in assumptions:
        var = abs(lit)
        expected_val = lit > 0
        assert assignment[var] == expected_val, (
            f"Model violates assumption {lit}: {var}={assignment[var]}"
        )

    # Check clauses
    for clause in cnf.clauses:
        clause_satisfied = any(
            (assignment[abs(lit)] if lit > 0 else not assignment[abs(lit)])
            for lit in clause
        )
        assert clause_satisfied, f"Model {assignment} violates clause {clause}"
