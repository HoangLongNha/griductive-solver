"""DPLL SAT solver implementation (task 3.1 & 3.2).

Features:
- Pure Python DPLL algorithm without third-party SAT solver dependencies.
- Unit propagation to fixpoint with conflict detection.
- Deterministic variable selection: smallest unassigned variable in an unsatisfied clause.
- Deterministic branching order: branch True first, then False.
- Complete assignment return for SAT results (all variables 1..variable_count).
- Non-mutating assumptions support (input CNF clauses remain immutable).
- Accurate stats counters: decisions, propagations, backtracks, runtime_s.
- SolverTimeout support for time-bounded runs.
"""
from __future__ import annotations

import time
from typing import Mapping

from griductive.models import (
    CNF,
    Clause,
    SATResult,
    SATStats,
    SolverCancelled,
    SolverTimeout,
)


def _validate_cnf_and_assumptions(cnf: CNF, assumptions: tuple[int, ...] | list[int]) -> None:
    """Validate structure and variable bounds of CNF and assumptions."""
    if not isinstance(cnf, CNF):
        raise TypeError(f"Expected CNF instance, got {type(cnf).__name__}")
    if type(cnf.variable_count) is not int or cnf.variable_count < 0:
        raise ValueError(f"variable_count must be a non-negative integer, got {cnf.variable_count}")
    if type(cnf.primary_count) is not int or not (0 <= cnf.primary_count <= cnf.variable_count):
        raise ValueError(
            f"primary_count must be in 0..{cnf.variable_count}, got {cnf.primary_count}"
        )

    for clause in cnf.clauses:
        for lit in clause:
            if type(lit) is not int or lit == 0:
                raise ValueError(f"Literal must be a non-zero integer, got {lit}")
            if abs(lit) > cnf.variable_count:
                raise ValueError(
                    f"Literal {lit} references variable {abs(lit)} > variable_count {cnf.variable_count}"
                )

    for lit in assumptions:
        if type(lit) is not int or lit == 0:
            raise ValueError(f"Assumption literal must be a non-zero integer, got {lit}")
        if abs(lit) > cnf.variable_count:
            raise ValueError(
                f"Assumption {lit} references variable {abs(lit)} > variable_count {cnf.variable_count}"
            )


class _DPLLRunner:
    """Internal recursive DPLL solver maintaining counters and immutable CNF access."""

    def __init__(
        self,
        cnf: CNF,
        assumptions: tuple[int, ...],
        timeout_s: float | None = None,
    ) -> None:
        self.cnf = cnf
        self.var_count = cnf.variable_count
        self.assumptions = assumptions
        self.timeout_s = timeout_s
        self.start_time = time.perf_counter()

        self.decisions = 0
        self.propagations = 0
        self.backtracks = 0

        # Preprocess and normalize clauses without mutating cnf.clauses
        self.clauses: list[tuple[int, ...]] = []
        self.has_empty_clause = False

        for clause in cnf.clauses:
            if len(clause) == 0:
                self.has_empty_clause = True
                break
            # Deduplicate literals while preserving order
            seen: set[int] = set()
            dedup: list[int] = []
            is_tautology = False
            for lit in clause:
                if -lit in seen:
                    is_tautology = True
                    break
                if lit not in seen:
                    seen.add(lit)
                    dedup.append(lit)
            if is_tautology:
                continue  # Tautologies are always satisfied under any assignment
            self.clauses.append(tuple(dedup))

    def _check_timeout(self) -> None:
        if self.timeout_s is not None:
            if time.perf_counter() - self.start_time > self.timeout_s:
                raise SolverTimeout(f"SAT solver exceeded timeout of {self.timeout_s}s")

    def _propagate(self, assignment: dict[int, bool]) -> bool:
        """Perform unit propagation until fixpoint. Return False on conflict, True otherwise."""
        while True:
            self._check_timeout()
            unit_lit: int | None = None

            for clause in self.clauses:
                has_true = False
                unassigned: list[int] = []

                for lit in clause:
                    v = abs(lit)
                    if v in assignment:
                        if assignment[v] == (lit > 0):
                            has_true = True
                            break
                    else:
                        unassigned.append(lit)

                if has_true:
                    continue
                if not unassigned:
                    # All literals false in an unsatisfied clause -> conflict
                    return False
                if len(unassigned) == 1 and unit_lit is None:
                    unit_lit = unassigned[0]

            if unit_lit is not None:
                v = abs(unit_lit)
                val = unit_lit > 0
                if v in assignment:
                    if assignment[v] != val:
                        return False
                else:
                    assignment[v] = val
                    self.propagations += 1
            else:
                return True

    def _is_satisfied(self, assignment: dict[int, bool]) -> bool:
        """Check whether every active clause has at least one true literal."""
        for clause in self.clauses:
            sat = False
            for lit in clause:
                v = abs(lit)
                if v in assignment and assignment[v] == (lit > 0):
                    sat = True
                    break
            if not sat:
                return False
        return True

    def _dpll(self, assignment: dict[int, bool]) -> bool:
        """Recursive DPLL branching and backtracking."""
        self._check_timeout()

        # Step 1: Unit propagation
        if not self._propagate(assignment):
            return False

        # Step 2: Deterministic variable selection: smallest unassigned variable ID among unsatisfied clauses
        unassigned_vars: set[int] = set()
        for clause in self.clauses:
            clause_sat = False
            clause_unassigned: list[int] = []
            for lit in clause:
                v = abs(lit)
                if v in assignment:
                    if assignment[v] == (lit > 0):
                        clause_sat = True
                        break
                else:
                    clause_unassigned.append(v)
            if not clause_sat:
                unassigned_vars.update(clause_unassigned)

        if not unassigned_vars:
            # All active clauses are satisfied!
            # Complete the model for any free/unassigned variables deterministically (default True)
            for v in range(1, self.var_count + 1):
                if v not in assignment:
                    assignment[v] = True
            return True

        branch_var = min(unassigned_vars)

        # Step 4: Branch True first, then False
        self.decisions += 1

        # Branch True
        saved = dict(assignment)
        assignment[branch_var] = True
        if self._dpll(assignment):
            return True

        # Backtrack from True branch
        self.backtracks += 1
        assignment.clear()
        assignment.update(saved)

        # Branch False
        assignment[branch_var] = False
        if self._dpll(assignment):
            return True

        # Backtrack from False branch
        self.backtracks += 1
        assignment.clear()
        assignment.update(saved)
        return False

    def run(self) -> SATResult:
        """Execute the solve query and return a frozen SATResult."""
        if self.has_empty_clause:
            runtime_s = time.perf_counter() - self.start_time
            stats = SATStats(
                decisions=0, propagations=0, backtracks=0, runtime_s=runtime_s
            )
            return SATResult(is_sat=False, assignment=None, stats=stats)

        # Process assumptions into initial assignment
        initial_assignment: dict[int, bool] = {}
        for lit in self.assumptions:
            v = abs(lit)
            val = lit > 0
            if v in initial_assignment:
                if initial_assignment[v] != val:
                    # Direct assumption contradiction (e.g. (+1, -1))
                    runtime_s = time.perf_counter() - self.start_time
                    stats = SATStats(
                        decisions=0, propagations=0, backtracks=0, runtime_s=runtime_s
                    )
                    return SATResult(is_sat=False, assignment=None, stats=stats)
            else:
                initial_assignment[v] = val

        assignment = dict(initial_assignment)
        is_sat = self._dpll(assignment)
        runtime_s = time.perf_counter() - self.start_time

        stats = SATStats(
            decisions=self.decisions,
            propagations=self.propagations,
            backtracks=self.backtracks,
            runtime_s=runtime_s,
        )

        if is_sat:
            # Ensure complete model: keys 1..var_count
            for v in range(1, self.var_count + 1):
                if v not in assignment:
                    assignment[v] = True
            return SATResult(is_sat=True, assignment=assignment, stats=stats)
        return SATResult(is_sat=False, assignment=None, stats=stats)


def solve(
    cnf: CNF,
    assumptions: tuple[int, ...] = (),
    *,
    timeout_s: float | None = None,
) -> SATResult:
    """Solve CNF with optional assumptions using DPLL.

    Args:
        cnf: The CNF formula containing clauses, primary_count, and variable_count.
        assumptions: Optional temporary unit literals to assume during this solve.
                     Input CNF is NOT modified.
        timeout_s: Optional maximum execution time in seconds. Raises SolverTimeout if exceeded.

    Returns:
        SATResult: If SAT, contains is_sat=True and complete assignment dict {1..variable_count}.
                   If UNSAT, contains is_sat=False and assignment=None.
                   Both cases include frozen SATStats counters.
    """
    _validate_cnf_and_assumptions(cnf, assumptions)
    runner = _DPLLRunner(cnf, assumptions, timeout_s=timeout_s)
    return runner.run()
