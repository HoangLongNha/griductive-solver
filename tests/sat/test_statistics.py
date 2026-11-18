"""Unit and acceptance tests for Task 3.2: SAT assumptions và thống kê.

Test IDs: STAT-01, STAT-02, STAT-03, STAT-04.
"""
import time
import pytest
from griductive.models import CNF, SATStats
from griductive.sat import (
    SolverStatsTracker,
    accumulate_stats,
    format_stats_summary,
    solve,
    zero_stats,
)


# =====================================================================
# Acceptance Tests: STAT-01 .. STAT-04
# =====================================================================


def test_stat01_assumption_contradicts_kb_unit():
    """STAT-01: Assumption +1 with KB unit clause (-1) returns UNSAT."""
    cnf = CNF(clauses=((-1,),), primary_count=1, variable_count=1)
    res = solve(cnf, assumptions=(1,))

    assert res.is_sat is False
    assert res.assignment is None
    assert res.stats.decisions == 0
    assert res.stats.propagations >= 0
    assert res.stats.runtime_s >= 0.0


def test_stat02_contradictory_assumptions():
    """STAT-02: Simultaneous assumptions (+1, -1) immediately return UNSAT."""
    cnf = CNF(clauses=((1, 2), (-2, 3)), primary_count=3, variable_count=3)
    res = solve(cnf, assumptions=(1, -1))

    assert res.is_sat is False
    assert res.assignment is None
    assert res.stats.decisions == 0
    assert res.stats.backtracks == 0
    assert res.stats.runtime_s >= 0.0


def test_stat03_input_cnf_immutability():
    """STAT-03: Input CNF clauses and fields remain strictly unmodified after solve."""
    clauses = ((1, 2), (-1, 2), (2, 3))
    cnf = CNF(clauses=clauses, primary_count=3, variable_count=3)

    # Solve multiple times with different assumptions
    solve(cnf, assumptions=(1,))
    solve(cnf, assumptions=(-1,))
    solve(cnf, assumptions=(1, -2))  # UNSAT
    solve(cnf, assumptions=(-2, -3))

    # Invariants: clause tuple identity and contents are completely unchanged
    assert cnf.clauses is clauses
    assert cnf.clauses == ((1, 2), (-1, 2), (2, 3))
    assert cnf.primary_count == 3
    assert cnf.variable_count == 3


def test_stat04_metrics_non_negative_and_consistent():
    """STAT-04: Stats counters are non-negative, runtime_s >= 0, and consistent."""
    cnf = CNF(clauses=((-1, 2), (-1, -2), (1, 2)), primary_count=2, variable_count=2)
    res1 = solve(cnf)
    res2 = solve(cnf)

    for res in (res1, res2):
        assert res.stats.decisions >= 0
        assert res.stats.propagations >= 0
        assert res.stats.backtracks >= 0
        assert res.stats.runtime_s >= 0.0
        assert isinstance(res.stats.decisions, int)
        assert isinstance(res.stats.propagations, int)
        assert isinstance(res.stats.backtracks, int)
        assert isinstance(res.stats.runtime_s, float)

    # Deterministic consistency
    assert res1.stats.decisions == res2.stats.decisions
    assert res1.stats.propagations == res2.stats.propagations
    assert res1.stats.backtracks == res2.stats.backtracks


# =====================================================================
# Additional coverage for assumptions & statistics utilities
# =====================================================================


def test_multiple_valid_assumptions_satisfaction():
    """Assumptions are satisfied by the returned model when problem is SAT."""
    cnf = CNF(clauses=((1, 2, 3), (-2, 3)), primary_count=3, variable_count=3)
    assumptions = (-1, 2)
    res = solve(cnf, assumptions=assumptions)

    assert res.is_sat is True
    assert res.assignment is not None
    # Model must honor assumptions
    assert res.assignment[1] is False
    assert res.assignment[2] is True
    # And model must satisfy all clauses
    for clause in cnf.clauses:
        assert any(
            res.assignment[abs(lit)] if lit > 0 else not res.assignment[abs(lit)]
            for lit in clause
        )


def test_assumptions_passed_as_list():
    """Assumptions can be passed as any sequence (e.g. list)."""
    cnf = CNF(clauses=((1, 2),), primary_count=2, variable_count=2)
    res = solve(cnf, assumptions=[1])
    assert res.is_sat is True
    assert res.assignment[1] is True


def test_solver_stats_tracker():
    """Test SolverStatsTracker operations."""
    tracker = SolverStatsTracker()
    tracker.record_decision()
    tracker.record_decision()
    tracker.record_propagation(3)
    tracker.record_backtrack()

    snap = tracker.snapshot()
    assert snap.decisions == 2
    assert snap.propagations == 3
    assert snap.backtracks == 1
    assert snap.runtime_s >= 0.0

    with pytest.raises(ValueError):
        tracker.record_propagation(-1)


def test_accumulate_stats_and_formatting():
    """Test accumulate_stats and format_stats_summary."""
    s1 = SATStats(decisions=2, propagations=5, backtracks=1, runtime_s=0.002)
    s2 = SATStats(decisions=3, propagations=1, backtracks=0, runtime_s=0.003)

    acc = accumulate_stats([s1, s2])
    assert acc.decisions == 5
    assert acc.propagations == 6
    assert acc.backtracks == 1
    assert abs(acc.runtime_s - 0.005) < 1e-6

    summary = format_stats_summary(acc)
    assert "decisions=5" in summary
    assert "propagations=6" in summary
    assert "backtracks=1" in summary
    assert "runtime=5.00ms" in summary

    # zero_stats
    z = zero_stats()
    assert z.decisions == 0
    assert z.propagations == 0
    assert z.backtracks == 0
    assert z.runtime_s == 0.0


def test_accumulate_stats_type_check():
    """accumulate_stats rejects non-SATStats objects."""
    with pytest.raises(TypeError):
        accumulate_stats([123])  # type: ignore
