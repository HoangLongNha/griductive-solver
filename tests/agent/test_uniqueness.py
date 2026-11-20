"""Acceptance and unit tests for Task 4.3: public Hint & full-clue Uniqueness checker.

Test IDs: HINT-01, UNIQ-01, UNIQ-02, UNIQ-03.
Uses test-only fake solvers and spy wrappers for unit isolation, plus integration
checks against VT1's `load_puzzle`/`GameSession` and VT2's `encode_kb`/`encode_full_clues`.
"""
from dataclasses import replace
from itertools import product
from pathlib import Path

import pytest

import griductive.agent as agent_pkg
from griductive.agent import (
    AgentVerdictOracle,
    HintOutcome,
    HintResult,
    QueryPurpose,
    SATQuery,
    TraceStatus,
    aggregate_queries,
    auto_solve,
    get_hint,
)
from griductive.game.engine import GameSession, load_puzzle
from griductive.logic import encode_full_clues, encode_kb
from griductive.models import (
    CNF,
    Clue,
    PublicCard,
    PublicState,
    SATResult,
    SATStats,
    SolverCancelled,
    SolverTimeout,
    Status,
    var_to_cell,
)
from griductive.validation import (
    UniquenessStatus,
    analyze_unique_cnf,
    analyze_unique_complete,
    build_primary_blocking_clause,
    check_unique_cnf,
    check_unique_complete,
)

ROOT = Path(__file__).resolve().parents[2]


def brute_force_test_solver(cnf: CNF, assumptions: tuple[int, ...] = ()) -> SATResult:
    """Test-only exhaustive SAT solver for small CNFs (NOT production DPLL)."""
    all_clauses = cnf.clauses + tuple((lit,) for lit in assumptions)
    stats = SATStats(decisions=2, propagations=3, backtracks=1, runtime_s=0.001)
    for bits in product((False, True), repeat=cnf.variable_count):
        assignment = {v: bits[v - 1] for v in range(1, cnf.variable_count + 1)}
        if all(
            any(assignment[abs(lit)] if lit > 0 else not assignment[abs(lit)] for lit in clause)
            for clause in all_clauses
        ):
            return SATResult(is_sat=True, assignment=assignment, stats=stats)
    return SATResult(is_sat=False, assignment=None, stats=stats)


def _make_2x2_public(
    revealed: dict[str, tuple[Status, Clue]],
    *,
    puzzle_id: str = "hint_2x2",
) -> PublicState:
    cards = []
    for var in range(1, 5):
        cell = var_to_cell(var, 2)
        if cell in revealed:
            status, clue = revealed[cell]
            cards.append(
                PublicCard(
                    cell=cell,
                    name=f"P{var}",
                    profession="Citizen",
                    revealed=True,
                    known_status=status,
                    clue=clue,
                )
            )
        else:
            cards.append(
                PublicCard(
                    cell=cell,
                    name=f"P{var}",
                    profession="Citizen",
                    revealed=False,
                    known_status=None,
                    clue=None,
                )
            )
    return PublicState(puzzle_id=puzzle_id, size=2, cards=tuple(cards))


# ---------------------------------------------------------------------------
# HINT-01: Public Hint tests
# ---------------------------------------------------------------------------


def test_hint_01_returns_first_row_major_forced_cell_and_revealed_clues():
    """HINT-01: Hint picks the first row-major forced cell using only PublicState."""
    # A1=CRIMINAL with SAME(A1, B2) forces B2=CRIMINAL;
    # A2=INNOCENT with DIFFERENT(A2, B1) forces B1=CRIMINAL.
    # Both B1 (var 2) and B2 (var 4) are forced -> row-major MUST pick B1 first.
    public = _make_2x2_public(
        {
            "A1": (Status.CRIMINAL, Clue("c-A1", "SAME", {"cells": ("A1", "B2")})),
            "A2": (Status.INNOCENT, Clue("c-A2", "DIFFERENT", {"cells": ("A2", "B1")})),
        }
    )
    log: list[SATQuery] = []
    hint = get_hint(public, encode_kb, brute_force_test_solver, query_log=log)

    assert hint.outcome == HintOutcome.FORCED
    assert hint.cell == "B1"
    assert hint.status == Status.CRIMINAL
    assert hint.revealed_clue_ids == ("c-A1", "c-A2")
    assert "B1" in hint.message and "CRIMINAL" in hint.message
    assert hint.queries == tuple(log)
    assert hint.stats == aggregate_queries(log)
    # First query is BASE_KB; all cell entailment queries are tagged HINT.
    assert log[0].purpose == QueryPurpose.BASE_KB
    assert all(q.purpose == QueryPurpose.HINT for q in log[1:])


def test_hint_01_no_forced_move_never_guesses():
    """HINT-01: When no cell is forced, Hint returns NO_FORCED_MOVE and never guesses."""
    puzzle = load_puzzle(str(ROOT / "puzzles/negative/ambiguous_3x3.json"))
    oracle = AgentVerdictOracle(encode_kb, brute_force_test_solver)
    session = GameSession(puzzle, oracle)

    hint = get_hint(session.snapshot(), encode_kb, brute_force_test_solver)
    assert hint.outcome == HintOutcome.NO_FORCED_MOVE
    assert hint.cell is None
    assert hint.status is None
    assert hint.revealed_clue_ids == ("c-A1",)


def test_hint_01_never_reads_hidden_labels_or_unrevealed_clues():
    """HINT-01: Identical PublicStates yield identical hints regardless of hidden data; Puzzle rejected."""
    from griductive.game.loader import PrivateCard, Puzzle

    puzzle_a = load_puzzle(str(ROOT / "puzzles/3x3/tutorial_3x3.json"))
    # Reject raw Puzzle directly at privacy gate.
    with pytest.raises(TypeError, match="PublicState"):
        get_hint(puzzle_a, encode_kb, brute_force_test_solver)  # type: ignore[arg-type]

    # Two puzzles with DIFFERENT hidden statuses and hidden clues on face-down cards
    # but IDENTICAL initial PublicState must produce identical hints.
    shared_a1 = PrivateCard(
        "A1", "Alice", "Chef", Status.CRIMINAL, Clue("c-A1", "FACT", {"cell": "B1", "status": "INNOCENT"})
    )
    priv_1 = Puzzle(
        id="hint_priv",
        size=2,
        initial_revealed=("A1",),
        cards=(
            shared_a1,
            PrivateCard("B1", "Bob", "Guard", Status.INNOCENT, Clue("c-B1-p1", "FACT", {"cell": "A2", "status": "CRIMINAL"})),
            PrivateCard("A2", "Cara", "Nurse", Status.CRIMINAL, Clue("c-A2-p1", "FACT", {"cell": "B2", "status": "CRIMINAL"})),
            PrivateCard("B2", "Dan", "Pilot", Status.CRIMINAL, Clue("c-B2-p1", "FACT", {"cell": "A1", "status": "CRIMINAL"})),
        ),
    )
    priv_2 = Puzzle(
        id="hint_priv",
        size=2,
        initial_revealed=("A1",),
        cards=(
            shared_a1,
            PrivateCard("B1", "Bob", "Guard", Status.INNOCENT, Clue("c-B1-p2", "FACT", {"cell": "A2", "status": "INNOCENT"})),
            PrivateCard("A2", "Cara", "Nurse", Status.INNOCENT, Clue("c-A2-p2", "FACT", {"cell": "B2", "status": "INNOCENT"})),
            PrivateCard("B2", "Dan", "Pilot", Status.INNOCENT, Clue("c-B2-p2", "FACT", {"cell": "A1", "status": "CRIMINAL"})),
        ),
    )
    oracle = AgentVerdictOracle(encode_kb, brute_force_test_solver)
    h1 = get_hint(GameSession(priv_1, oracle).snapshot(), encode_kb, brute_force_test_solver)
    h2 = get_hint(GameSession(priv_2, oracle).snapshot(), encode_kb, brute_force_test_solver)
    assert h1 == h2
    assert h1.outcome == HintOutcome.FORCED
    assert h1.cell == "B1"
    assert h1.status == Status.INNOCENT
    assert h1.revealed_clue_ids == ("c-A1",)
    for hidden_clue_id in ("c-B1-p1", "c-A2-p1", "c-B2-p1", "c-B1-p2", "c-A2-p2", "c-B2-p2"):
        assert hidden_clue_id not in h1.revealed_clue_ids
        assert hidden_clue_id not in h1.message


def test_hint_solved_and_inconsistent_states():
    """Hint checks KB consistency even when all cards are revealed."""
    solved_public = _make_2x2_public(
        {
            "A1": (Status.CRIMINAL, Clue("c-A1", "FACT", {"cell": "A1", "status": "CRIMINAL"})),
            "B1": (Status.INNOCENT, Clue("c-B1", "FACT", {"cell": "B1", "status": "INNOCENT"})),
            "A2": (Status.CRIMINAL, Clue("c-A2", "FACT", {"cell": "A2", "status": "CRIMINAL"})),
            "B2": (Status.INNOCENT, Clue("c-B2", "FACT", {"cell": "B2", "status": "INNOCENT"})),
        }
    )
    solved_log: list[SATQuery] = []
    solved_hint = get_hint(solved_public, encode_kb, brute_force_test_solver, query_log=solved_log)
    assert solved_hint.outcome == HintOutcome.SOLVED
    assert solved_hint.cell is None
    assert solved_hint.status is None
    assert solved_hint.stats.sat_calls == 1
    assert solved_hint.queries == tuple(solved_log)
    assert solved_log[0].purpose == QueryPurpose.BASE_KB

    inconsistent_full_public = replace(
        solved_public,
        cards=(
            replace(
                solved_public.cards[0],
                clue=Clue("c-A1", "FACT", {"cell": "A1", "status": "INNOCENT"}),
            ),
            *solved_public.cards[1:],
        ),
    )
    full_log: list[SATQuery] = []
    full_hint = get_hint(
        inconsistent_full_public, encode_kb, brute_force_test_solver, query_log=full_log
    )
    assert full_hint.outcome == HintOutcome.INCONSISTENT
    assert full_hint.cell is None and full_hint.status is None
    assert full_hint.stats.sat_calls == 1
    assert full_hint.queries == tuple(full_log)
    assert full_log[0].purpose == QueryPurpose.BASE_KB

    inconsistent_public = _make_2x2_public(
        {
            "A1": (Status.CRIMINAL, Clue("c-A1", "FACT", {"cell": "A1", "status": "INNOCENT"})),
        }
    )
    inc_hint = get_hint(inconsistent_public, encode_kb, brute_force_test_solver)
    assert inc_hint.outcome == HintOutcome.INCONSISTENT
    assert inc_hint.cell is None
    assert inc_hint.status is None
    assert inc_hint.stats.sat_calls == 1


def test_hint_propagates_timeout_and_cancelled():
    """Unfinished queries propagate untouched from get_hint."""
    public = _make_2x2_public(
        {"A1": (Status.CRIMINAL, Clue("c-A1", "FACT", {"cell": "B1", "status": "INNOCENT"}))}
    )

    def timeout_solver(cnf: CNF, assumptions: tuple[int, ...] = ()) -> SATResult:
        raise SolverTimeout("deadline exceeded")

    def cancel_solver(cnf: CNF, assumptions: tuple[int, ...] = ()) -> SATResult:
        raise SolverCancelled("user cancelled")

    with pytest.raises(SolverTimeout):
        get_hint(public, encode_kb, timeout_solver)
    with pytest.raises(SolverCancelled):
        get_hint(public, encode_kb, cancel_solver)


def test_hint_result_validates_invariants():
    """HintResult enforces consistency between outcome and (cell, status)."""
    with pytest.raises(ValueError):
        HintResult(HintOutcome.FORCED, None, Status.CRIMINAL, (), "bad")
    with pytest.raises(ValueError):
        HintResult(HintOutcome.NO_FORCED_MOVE, "A1", Status.CRIMINAL, (), "bad")


# ---------------------------------------------------------------------------
# UNIQ-01, UNIQ-02, UNIQ-03: Full-clue Uniqueness Checker tests
# ---------------------------------------------------------------------------


def test_uniq_01_single_primary_model_returns_true():
    """UNIQ-01: CNF with exactly one primary model returns unique=True in 2 UNIQUENESS calls."""
    # Forces 1=True, 2=False, 3=True uniquely.
    cnf = CNF(clauses=((1,), (-2,), (3,)), primary_count=3, variable_count=3)
    log: list[SATQuery] = []

    result = analyze_unique_cnf(cnf, brute_force_test_solver, query_log=log)
    assert result.is_unique is True
    assert result.status == UniquenessStatus.UNIQUE
    assert result.first_model == {1: True, 2: False, 3: True}
    assert result.second_model is None
    assert result.blocking_clause == (-1, 2, -3)
    assert len(log) == 2
    assert all(q.purpose == QueryPurpose.UNIQUENESS for q in log)
    assert result.stats == aggregate_queries(log)
    assert check_unique_cnf(cnf, brute_force_test_solver) is True


def test_uniq_01_single_primary_model_with_multiple_aux_completions_is_still_unique():
    """UNIQ-01 + UNIQ-03: Multiple auxiliary completions of the SAME primary model => unique=True."""
    # Primary vars: 1, 2, 3 uniquely forced to (True, False, True).
    # Auxiliary vars: 4, 5 constrained only by (4 v 5) -> 3 distinct aux completions!
    # A buggy checker that included aux vars in the blocking clause would falsely report False.
    cnf = CNF(
        clauses=((1,), (-2,), (3,), (4, 5)),
        primary_count=3,
        variable_count=5,
    )
    result = analyze_unique_cnf(cnf, brute_force_test_solver)

    assert result.is_unique is True
    assert result.status == UniquenessStatus.UNIQUE
    assert result.first_model == {1: True, 2: False, 3: True}
    assert set(result.first_model.keys()) == {1, 2, 3}  # no aux variables exposed
    assert result.second_model is None
    assert result.blocking_clause == (-1, 2, -3)


def test_uniq_02_multiple_primary_models_returns_false():
    """UNIQ-02: CNF with >= 2 distinct primary models returns unique=False and both models."""
    # 1=True, 2=False, 3 is unconstrained -> two primary models (3=False and 3=True).
    cnf = CNF(clauses=((1,), (-2,)), primary_count=3, variable_count=3)

    result = analyze_unique_cnf(cnf, brute_force_test_solver)
    assert result.is_unique is False
    assert result.status == UniquenessStatus.MULTIPLE
    assert result.first_model is not None
    assert result.second_model is not None
    assert result.first_model != result.second_model
    assert result.stats.sat_calls == 2
    assert check_unique_cnf(cnf, brute_force_test_solver) is False


def test_uniq_02_unsat_cnf_returns_false_in_one_call():
    """UNIQ-02 edge case: Unsatisfiable CNF returns unique=False (UNSAT) after 1 SAT call."""
    cnf = CNF(clauses=((1,), (-1,)), primary_count=2, variable_count=2)

    result = analyze_unique_cnf(cnf, brute_force_test_solver)
    assert result.is_unique is False
    assert result.status == UniquenessStatus.UNSAT
    assert result.first_model is None
    assert result.second_model is None
    assert result.blocking_clause is None
    assert result.stats.sat_calls == 1
    assert check_unique_cnf(cnf, brute_force_test_solver) is False


def test_uniq_03_blocking_clause_strictly_primary_only_and_input_cnf_immutable():
    """UNIQ-03: Directly inspect the blocking clause passed to SAT call #2."""
    original_clauses = ((1,), (-2,), (3,), (4, 5), (-4, 6))
    cnf = CNF(clauses=original_clauses, primary_count=3, variable_count=6)
    seen_cnfs: list[CNF] = []

    def spy_solver(received_cnf: CNF, assumptions: tuple[int, ...] = ()) -> SATResult:
        seen_cnfs.append(received_cnf)
        assert assumptions == ()
        return brute_force_test_solver(received_cnf, assumptions)

    assert check_unique_cnf(cnf, spy_solver) is True
    assert len(seen_cnfs) == 2

    # First call receives original clauses; second call appends exactly one blocking clause.
    assert seen_cnfs[0].clauses == original_clauses
    assert seen_cnfs[1].clauses[:-1] == original_clauses
    assert len(seen_cnfs[1].clauses) == len(original_clauses) + 1

    blocking_clause = seen_cnfs[1].clauses[-1]
    assert len(blocking_clause) == cnf.primary_count == 3
    assert all(1 <= abs(lit) <= cnf.primary_count for lit in blocking_clause)
    assert blocking_clause == (-1, 2, -3)

    # Original CNF object must remain completely untouched.
    assert cnf.clauses == original_clauses


def test_build_primary_blocking_clause_validation():
    """Helper rejects invalid primary_count, missing vars, or non-bool values."""
    assert build_primary_blocking_clause({1: True, 2: False, 3: True, 4: True}, 3) == (-1, 2, -3)

    with pytest.raises(ValueError):
        build_primary_blocking_clause({1: True}, 0)
    with pytest.raises(ValueError):
        build_primary_blocking_clause({1: True}, 2)
    with pytest.raises(TypeError):
        build_primary_blocking_clause({1: 1}, 1)  # type: ignore[dict-item]


def test_uniq_complete_on_real_fixtures_and_independence_from_no_guess_playability():
    """Real fixtures: tutorial/extensions are unique; ambiguous_3x3 is unique yet STUCK."""
    tutorial = load_puzzle(str(ROOT / "puzzles/3x3/tutorial_3x3.json"))
    extensions = load_puzzle(str(ROOT / "puzzles/3x3/extensions_3x3.json"))
    ambiguous = load_puzzle(str(ROOT / "puzzles/negative/ambiguous_3x3.json"))

    tut_res = analyze_unique_complete(tutorial, encode_full_clues, brute_force_test_solver)
    assert tut_res.is_unique is True
    assert tut_res.status == UniquenessStatus.UNIQUE
    assert all(q.purpose == QueryPurpose.UNIQUENESS for q in tut_res.queries)

    assert check_unique_complete(extensions, encode_full_clues, brute_force_test_solver) is True

    # Crucial contract invariant (CONTRACTS §5):
    # ambiguous_3x3 has a UNIQUE complete clue solution, yet is NOT no-guess playable from start!
    assert check_unique_complete(ambiguous, encode_full_clues, brute_force_test_solver) is True

    oracle = AgentVerdictOracle(encode_kb, brute_force_test_solver)
    amb_session = GameSession(ambiguous, oracle)
    assert get_hint(amb_session.snapshot(), encode_kb, brute_force_test_solver).outcome == HintOutcome.NO_FORCED_MOVE
    trace = auto_solve(amb_session, encode_kb, brute_force_test_solver)
    assert trace.status == TraceStatus.STUCK
    assert trace.deduction_steps == 0


def test_uniq_02_complete_puzzle_with_multiple_solutions_returns_false():
    """UNIQ-02 with real `encode_full_clues`: under-constrained 2x2 puzzle returns MULTIPLE/False."""
    from griductive.game.loader import PrivateCard, Puzzle

    # A1=CRIMINAL, B1=INNOCENT, A2=CRIMINAL, while B2 is left unconstrained by all 4 clues.
    under_constrained = Puzzle(
        id="multi_2x2",
        size=2,
        initial_revealed=("A1",),
        cards=(
            PrivateCard("A1", "Alice", "Chef", Status.CRIMINAL, Clue("c-A1", "FACT", {"cell": "A1", "status": "CRIMINAL"})),
            PrivateCard("B1", "Bob", "Guard", Status.INNOCENT, Clue("c-B1", "FACT", {"cell": "B1", "status": "INNOCENT"})),
            PrivateCard("A2", "Cara", "Nurse", Status.CRIMINAL, Clue("c-A2", "FACT", {"cell": "A2", "status": "CRIMINAL"})),
            PrivateCard("B2", "Dan", "Pilot", Status.INNOCENT, Clue("c-B2", "SAME", {"cells": ("A1", "A2")})),
        ),
    )

    res = analyze_unique_complete(under_constrained, encode_full_clues, brute_force_test_solver)
    assert res.is_unique is False
    assert res.status == UniquenessStatus.MULTIPLE
    assert res.first_model is not None and res.second_model is not None
    assert res.first_model[4] != res.second_model[4]  # B2 differs between the two solutions
    assert check_unique_complete(under_constrained, encode_full_clues, brute_force_test_solver) is False


def test_uniq_scope_separation_and_error_handling():
    """Validation scope is strictly separate from public agent; errors propagate cleanly."""
    # Public agent package must NOT expose validation-only uniqueness APIs.
    assert not hasattr(agent_pkg, "check_unique_complete")
    assert not hasattr(agent_pkg, "check_unique_cnf")

    # Passing PublicState to check_unique_complete is rejected.
    public = _make_2x2_public(
        {"A1": (Status.CRIMINAL, Clue("c-A1", "FACT", {"cell": "B1", "status": "INNOCENT"}))}
    )
    with pytest.raises(TypeError, match="Puzzle"):
        check_unique_complete(public, encode_full_clues, brute_force_test_solver)

    # Timeout/cancel on call #2 must propagate and NEVER be mistaken for UNSAT/UNIQUE!
    cnf = CNF(clauses=((1,), (-2,)), primary_count=2, variable_count=2)
    calls = 0

    def timeout_on_second(received_cnf: CNF, assumptions: tuple[int, ...] = ()) -> SATResult:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise SolverTimeout("second call timed out")
        return brute_force_test_solver(received_cnf, assumptions)

    log: list[SATQuery] = []
    with pytest.raises(SolverTimeout):
        check_unique_cnf(cnf, timeout_on_second, query_log=log)
    assert len(log) == 1  # Call #1 completed and was logged before call #2 timed out.

    def cancel_on_first(received_cnf: CNF, assumptions: tuple[int, ...] = ()) -> SATResult:
        raise SolverCancelled("cancelled")

    with pytest.raises(SolverCancelled):
        check_unique_cnf(cnf, cancel_on_first)

    # Defensive check: a buggy solver ignoring blocking clause is detected.
    def buggy_ignoring_solver(received_cnf: CNF, assumptions: tuple[int, ...] = ()) -> SATResult:
        return SATResult(
            is_sat=True,
            assignment={1: True, 2: False},
            stats=SATStats(0, 0, 0, 0.0),
        )

    with pytest.raises(ValueError, match="violating the primary blocking clause"):
        analyze_unique_cnf(cnf, buggy_ignoring_solver)
