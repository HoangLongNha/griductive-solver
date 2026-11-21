"""Acceptance and unit tests for Task 4.2: deduction loop & trace.

Test IDs: AGL-01, AGL-02, AGL-03, AGL-04, AGL-05.
Uses `FakeGamePort` + fake solver for unit isolation, plus end-to-end checks
against VT1's `GameSession` and VT2's `encode_kb` on 3x3 fixtures.
"""
from itertools import product
from pathlib import Path

import pytest

from griductive.agent import (
    AgentVerdictOracle,
    QueryPurpose,
    TraceStatus,
    aggregate_queries,
    auto_solve,
    next_forced_verdict,
    select_forced_verdict,
)
from griductive.game.engine import GameSession, load_puzzle
from griductive.logic import encode_kb
from griductive.models import (
    CNF,
    CellId,
    Clue,
    Inference,
    PublicCard,
    PublicState,
    SATResult,
    SATStats,
    SolverTimeout,
    Status,
    SubmitResult,
    VerdictStatus,
    cell_to_var,
    var_to_cell,
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


class FakeGamePort:
    """Minimal `PublicGamePort` fake for testing `auto_solve` without real Engine."""

    def __init__(
        self,
        size: int,
        solution: dict[CellId, Status],
        clues: dict[CellId, Clue],
        initial_revealed: set[CellId],
        *,
        force_outcome: VerdictStatus | None = None,
        skip_reveal_on_accept: bool = False,
    ):
        self.size = size
        self.solution = dict(solution)
        self.clues = dict(clues)
        self.revealed = set(initial_revealed)
        self.force_outcome = force_outcome
        self.skip_reveal_on_accept = skip_reveal_on_accept
        self.snapshot_calls = 0
        self.submissions: list[tuple[CellId, Status]] = []

    def snapshot(self) -> PublicState:
        self.snapshot_calls += 1
        cards = []
        for var in range(1, self.size * self.size + 1):
            cell = var_to_cell(var, self.size)
            shown = cell in self.revealed
            cards.append(
                PublicCard(
                    cell=cell,
                    name=f"P{var}",
                    profession="Citizen",
                    revealed=shown,
                    known_status=self.solution[cell] if shown else None,
                    clue=self.clues[cell] if shown else None,
                )
            )
        return PublicState(puzzle_id=f"fake_{self.size}x{self.size}", size=self.size, cards=tuple(cards))

    def submit_verdict(self, cell: CellId, status: Status) -> SubmitResult:
        self.submissions.append((cell, status))
        if self.force_outcome is not None:
            return SubmitResult(
                outcome=self.force_outcome,
                state=self.snapshot(),
                newly_revealed=None,
                message=f"Forced {self.force_outcome.value}",
            )
        if self.solution[cell] != status:
            return SubmitResult(
                outcome=VerdictStatus.CONTRADICTED,
                state=self.snapshot(),
                newly_revealed=None,
                message="Contradicts hidden truth",
            )
        if not self.skip_reveal_on_accept:
            self.revealed.add(cell)
        return SubmitResult(
            outcome=VerdictStatus.ACCEPTED,
            state=self.snapshot(),
            newly_revealed=None if self.skip_reveal_on_accept else cell,
            message="Accepted",
        )


def make_chain_2x2_game() -> FakeGamePort:
    """2x2 puzzle solved strictly in 3 steps: A1 -> B1 -> A2 -> B2."""
    solution = {
        "A1": Status.CRIMINAL,
        "B1": Status.INNOCENT,
        "A2": Status.CRIMINAL,
        "B2": Status.INNOCENT,
    }
    clues = {
        "A1": Clue("c-A1", "FACT", {"cell": "B1", "status": "INNOCENT"}),
        "B1": Clue("c-B1", "DIFFERENT", {"cells": ["B1", "A2"]}),
        "A2": Clue("c-A2", "DIFFERENT", {"cells": ["A2", "B2"]}),
        "B2": Clue("c-B2", "FACT", {"cell": "A1", "status": "CRIMINAL"}),
    }
    return FakeGamePort(2, solution, clues, initial_revealed={"A1"})


# =====================================================================
# Acceptance tests: AGL-01 .. AGL-05
# =====================================================================


def test_agl01_row_major_selection_when_multiple_forced():
    """AGL-01: When multiple cells are forced, always pick the first in row-major order."""
    # Row-major 2x2 order is A1, B1, A2, B2.
    # Make A1 reveal an EXACTLY(2) clue on {B1, B2} => BOTH B1 and B2 are forced CRIMINAL!
    solution = {
        "A1": Status.INNOCENT,
        "B1": Status.CRIMINAL,
        "A2": Status.INNOCENT,
        "B2": Status.CRIMINAL,
    }
    clues = {
        "A1": Clue("c-A1", "EXACTLY", {"k": 2, "region": {"type": "cells", "cells": ["B2", "B1"]}}),
        "B1": Clue("c-B1", "FACT", {"cell": "A2", "status": "INNOCENT"}),
        "A2": Clue("c-A2", "FACT", {"cell": "A1", "status": "INNOCENT"}),
        "B2": Clue("c-B2", "FACT", {"cell": "A1", "status": "INNOCENT"}),
    }
    game = FakeGamePort(2, solution, clues, initial_revealed={"A1"})
    state = game.snapshot()

    # Pure selector test with reversed dict insertion order
    chosen = select_forced_verdict(
        state,
        {"B2": Inference.CRIMINAL, "A2": Inference.UNKNOWN, "B1": Inference.CRIMINAL},
    )
    assert chosen == ("B1", Status.CRIMINAL)

    # Through next_forced_verdict with real encoder
    assert next_forced_verdict(state, encode_kb, brute_force_test_solver) == ("B1", Status.CRIMINAL)

    # Full loop picks B1 first, then B1 reveals clue forcing A2 (comes before B2 row-major!), then B2
    trace = auto_solve(game, encode_kb, brute_force_test_solver)
    assert trace.status == TraceStatus.SOLVED
    assert [step.cell for step in trace.steps] == ["B1", "A2", "B2"]


def test_agl02_accepted_rebuild_kb_and_continue_to_solved():
    """AGL-02: Accepted verdict -> fresh snapshot -> rebuilt KB -> continue until SOLVED."""
    game = make_chain_2x2_game()
    trace = auto_solve(game, encode_kb, brute_force_test_solver)

    assert trace.status == TraceStatus.SOLVED
    assert trace.deduction_steps == 3
    assert [(s.cell, s.verdict) for s in trace.steps] == [
        ("B1", Status.INNOCENT),
        ("A2", Status.CRIMINAL),
        ("B2", Status.INNOCENT),
    ]
    # Active clues grow strictly after every accepted reveal
    assert [s.active_clue_ids for s in trace.steps] == [
        ("c-A1",),
        ("c-A1", "c-B1"),
        ("c-A1", "c-B1", "c-A2"),
    ]
    assert all(card.revealed for card in trace.final_state.cards)


def test_agl03_stuck_when_no_forced_verdict_and_never_guesses():
    """AGL-03: No forced cell -> STUCK immediately, zero submissions, no card revealed."""
    solution = {
        "A1": Status.INNOCENT,
        "B1": Status.CRIMINAL,
        "A2": Status.CRIMINAL,
        "B2": Status.INNOCENT,
    }
    clues = {
        # A1's clue only restates A1 -> says nothing about B1, A2, B2
        "A1": Clue("c-A1", "FACT", {"cell": "A1", "status": "INNOCENT"}),
        "B1": Clue("c-B1", "FACT", {"cell": "B1", "status": "CRIMINAL"}),
        "A2": Clue("c-A2", "FACT", {"cell": "A2", "status": "CRIMINAL"}),
        "B2": Clue("c-B2", "FACT", {"cell": "B2", "status": "INNOCENT"}),
    }
    game = FakeGamePort(2, solution, clues, initial_revealed={"A1"})

    trace = auto_solve(game, encode_kb, brute_force_test_solver)
    assert trace.status == TraceStatus.STUCK
    assert trace.deduction_steps == 0
    assert game.submissions == []
    assert game.revealed == {"A1"}
    # Terminal queries are still recorded and summed into totals
    assert trace.total_sat_calls == len(trace.terminal_queries) == 7  # 1 BASE_KB + 2*3 CLASSIFY


def test_agl04_trace_records_step_clues_queries_verdict_reveal_and_exact_totals():
    """AGL-04: Trace records step index, active clues, SAT queries/results, verdict, new clue & stats."""
    game = make_chain_2x2_game()
    trace = auto_solve(game, encode_kb, brute_force_test_solver)

    assert trace.puzzle_id == "fake_2x2"
    step1 = trace.steps[0]
    assert step1.step_index == 1
    assert step1.active_clue_ids == ("c-A1",)
    assert step1.cnf_metrics.primary_count == 4
    assert step1.cnf_metrics.aux_count == 0
    assert step1.cnf_metrics.clause_count == 2  # unit(A1=CRIMINAL) + FACT(B1=INNOCENT)
    assert step1.cell == "B1"
    assert step1.verdict == Status.INNOCENT
    assert step1.outcome == VerdictStatus.ACCEPTED
    assert step1.newly_revealed_cell == "B1"
    assert step1.newly_revealed_clue_id == "c-B1"

    # Verify per-step query audit log
    assert step1.queries[0].purpose == QueryPurpose.BASE_KB
    assert step1.queries[0].assumptions == ()
    assert step1.queries[0].is_sat is True
    b1_var = cell_to_var("B1", 2)
    b1_qs = [q for q in step1.queries if q.target_cell == "B1"]
    assert [(q.assumptions, q.is_sat) for q in b1_qs] == [((-b1_var,), True), ((b1_var,), False)]

    # Contracts §7: aggregate totals MUST equal exact sum of per-call logs
    assert step1.stats == aggregate_queries(step1.queries)
    assert trace.totals == aggregate_queries(trace.all_queries)
    assert trace.total_sat_calls == sum(len(s.queries) for s in trace.steps) + len(trace.terminal_queries)
    assert trace.totals.sat_runtime_s >= 0.0
    assert trace.total_runtime_s >= 0.0


def test_agl05_inconsistent_kb_or_contradicted_verdict_creates_no_reveal():
    """AGL-05: Inconsistent KB or CONTRADICTED verdict stops immediately with no reveal."""
    # Case 1: Inconsistent public KB (A1 is CRIMINAL, yet clue says A1 is INNOCENT)
    solution = {
        "A1": Status.CRIMINAL,
        "B1": Status.INNOCENT,
        "A2": Status.INNOCENT,
        "B2": Status.INNOCENT,
    }
    clues = {
        "A1": Clue("c-A1", "FACT", {"cell": "A1", "status": "INNOCENT"}),
        "B1": Clue("c-B1", "FACT", {"cell": "B1", "status": "INNOCENT"}),
        "A2": Clue("c-A2", "FACT", {"cell": "A2", "status": "INNOCENT"}),
        "B2": Clue("c-B2", "FACT", {"cell": "B2", "status": "INNOCENT"}),
    }
    inconsistent_game = FakeGamePort(2, solution, clues, initial_revealed={"A1"})
    trace1 = auto_solve(inconsistent_game, encode_kb, brute_force_test_solver)

    assert trace1.status == TraceStatus.INCONSISTENT
    assert trace1.deduction_steps == 0
    assert inconsistent_game.submissions == []
    assert inconsistent_game.revealed == {"A1"}
    assert len(trace1.terminal_queries) == 1  # Stopped after BASE_KB UNSAT

    # Case 2: Engine rejects forced verdict with CONTRADICTED -> stops, no reveal
    contradicted_game = make_chain_2x2_game()
    contradicted_game.force_outcome = VerdictStatus.CONTRADICTED
    trace2 = auto_solve(contradicted_game, encode_kb, brute_force_test_solver)

    assert trace2.status == TraceStatus.INCONSISTENT
    assert trace2.deduction_steps == 0
    assert contradicted_game.revealed == {"A1"}
    assert contradicted_game.submissions == [("B1", Status.INNOCENT)]


# =====================================================================
# Real fixture & defensive edge-case checks
# =====================================================================


@pytest.mark.parametrize(
    "fixture_rel",
    ["puzzles/3x3/tutorial_3x3.json", "puzzles/3x3/extensions_3x3.json"],
)
def test_auto_solve_with_real_game_session_and_encoder_3x3(fixture_rel):
    """End-to-end check on 3x3 fixtures with real GameSession + real encode_kb + test solver."""
    puzzle = load_puzzle(str(ROOT / fixture_rel))
    oracle = AgentVerdictOracle(encode_kb, brute_force_test_solver)
    game = GameSession(puzzle, oracle)

    trace = auto_solve(game, encode_kb, brute_force_test_solver)
    assert trace.status == TraceStatus.SOLVED
    assert trace.deduction_steps == puzzle.size * puzzle.size - len(puzzle.initial_revealed)
    assert all(card.revealed for card in trace.final_state.cards)
    assert trace.totals == aggregate_queries(trace.all_queries)


def test_auto_solve_ambiguous_fixture_stops_stuck():
    """Ambiguous 3x3 fixture stops at STUCK without guessing."""
    puzzle = load_puzzle(str(ROOT / "puzzles/negative/ambiguous_3x3.json"))
    oracle = AgentVerdictOracle(encode_kb, brute_force_test_solver)
    game = GameSession(puzzle, oracle)

    trace = auto_solve(game, encode_kb, brute_force_test_solver)
    assert trace.status == TraceStatus.STUCK
    assert trace.deduction_steps == 0
    assert sum(1 for c in trace.final_state.cards if c.revealed) == len(puzzle.initial_revealed)


def test_auto_solve_defensive_edges():
    """Handles already-solved board, non-revealing broken port, and SolverTimeout cleanly."""
    # Already-solved board -> SOLVED with 0 steps
    solved_game = make_chain_2x2_game()
    solved_game.revealed = {"A1", "B1", "A2", "B2"}
    trace = auto_solve(solved_game, encode_kb, brute_force_test_solver)
    assert trace.status == TraceStatus.SOLVED
    assert trace.deduction_steps == 0
    assert trace.total_sat_calls == 0

    # Broken port that accepts without revealing -> stops cleanly instead of infinite loop
    broken_game = make_chain_2x2_game()
    broken_game.skip_reveal_on_accept = True
    broken_trace = auto_solve(broken_game, encode_kb, brute_force_test_solver)
    assert broken_trace.status == TraceStatus.INCONSISTENT
    assert broken_trace.deduction_steps == 0

    # SolverTimeout propagates without revealing any card
    timeout_game = make_chain_2x2_game()

    def timeout_solver(cnf, assumptions=()):
        raise SolverTimeout("budget exhausted")

    with pytest.raises(SolverTimeout):
        auto_solve(timeout_game, encode_kb, timeout_solver)
    assert timeout_game.submissions == []
    assert timeout_game.revealed == {"A1"}


def test_agl04_trace_privacy_never_leaks_hidden_clues_or_statuses():
    """Task 4.2c: DeductionTrace must never expose hidden clue IDs or statuses of unrevealed cards."""
    puzzle = load_puzzle(str(ROOT / "puzzles/negative/ambiguous_3x3.json"))
    oracle = AgentVerdictOracle(encode_kb, brute_force_test_solver)
    game = GameSession(puzzle, oracle)

    trace = auto_solve(game, encode_kb, brute_force_test_solver)
    assert trace.terminal == TraceStatus.STUCK

    hidden_clue_ids = {c.clue.id for c in puzzle.cards if c.cell not in puzzle.initial_revealed}
    for card in trace.final_state.cards:
        if not card.revealed:
            assert card.known_status is None
            assert card.clue is None

    serialized_trace = repr(trace)
    for secret_id in hidden_clue_ids:
        assert secret_id not in serialized_trace


def test_shared_13a_walkthrough_and_on_step_streaming_callback():
    """Notion v0.2 shared 1.3a walkthrough + `on_step` streaming callback & `cumulative_stats`."""
    puzzle = load_puzzle(str(ROOT / "puzzles/3x3/tutorial_3x3.json"))
    oracle = AgentVerdictOracle(encode_kb, brute_force_test_solver)
    game = GameSession(puzzle, oracle)
    streamed_steps = []

    trace = auto_solve(game, encode_kb, brute_force_test_solver, on_step=streamed_steps.append)
    assert trace.terminal == TraceStatus.SOLVED
    assert tuple(streamed_steps) == trace.steps

    # Shared 1.3a Step 1: only c-A1 active -> proves B1 INNOCENT -> reveals c-B1
    s1 = trace.steps[0]
    assert s1.step_number == 1
    assert s1.active_clue_ids == ("c-A1",)
    assert (s1.cell, s1.verdict) == ("B1", Status.INNOCENT)
    assert s1.newly_revealed_clue_id == "c-B1"
    b1_classify_qs = [(q.assumptions, q.is_sat) for q in s1.queries if q.target_cell == "B1" and q.purpose == QueryPurpose.CLASSIFY]
    assert b1_classify_qs == [((-2,), True), ((2,), False)]
    b1_recheck_qs = [(q.assumptions, q.is_sat) for q in s1.queries if q.target_cell == "B1" and q.purpose == QueryPurpose.VERDICT_RECHECK]
    assert b1_recheck_qs == [((-2,), True), ((2,), False)]
    c1_qs_step1 = [(q.assumptions, q.is_sat) for q in s1.queries if q.target_cell == "C1"]
    assert c1_qs_step1 == [((-3,), True), ((3,), True)]  # C1 was still UNKNOWN before B1 revealed

    # Shared 1.3a Step 2: c-B1 = SAME(B1, C1) added -> proves C1 INNOCENT
    s2 = trace.steps[1]
    assert s2.step_number == 2
    assert s2.active_clue_ids == ("c-A1", "c-B1")
    assert (s2.cell, s2.verdict) == ("C1", Status.INNOCENT)
    assert s2.newly_revealed_clue_id == "c-C1"

    # Cumulative stats grow monotonically and final step cumulative_stats matches trace.totals (since SOLVED has no terminal_queries)
    prev_calls = 0
    for step in trace.steps:
        assert step.cumulative_stats.sat_calls == prev_calls + step.stats.sat_calls
        prev_calls = step.cumulative_stats.sat_calls
    assert trace.steps[-1].cumulative_stats == trace.totals


def test_agl04_trace_records_engine_verdict_recheck_queries_and_matches_real_solver_calls():
    """Contracts §7 & AGL-04: total_sat_calls must include Engine submit_verdict verification queries.
    
    Validates on tutorial_3x3 with counting solver: 8 steps x 3 verification queries = 24 calls,
    plus 80 classify queries = exactly 104 calls in both trace.total_sat_calls and solver.call_count.
    """
    puzzle = load_puzzle(str(ROOT / "puzzles/3x3/tutorial_3x3.json"))
    real_calls = 0

    def counting_solver(cnf: CNF, assumptions: tuple[int, ...] = ()) -> SATResult:
        nonlocal real_calls
        real_calls += 1
        return brute_force_test_solver(cnf, assumptions)

    oracle = AgentVerdictOracle(encode_kb, counting_solver)
    game = GameSession(puzzle, oracle)

    trace = auto_solve(game, encode_kb, counting_solver)
    assert trace.terminal == TraceStatus.SOLVED
    assert trace.deduction_steps == 8

    # Each step includes the classification queries plus the engine recheck queries (QueryPurpose.VERDICT_RECHECK)
    for step in trace.steps:
        recheck_qs = [q for q in step.queries if q.purpose == QueryPurpose.VERDICT_RECHECK]
        assert len(recheck_qs) == 2  # (-v,) and (v,) assumptions evaluated during submit_verdict

    assert trace.total_sat_calls == real_calls == 104


def test_agl04_pure_public_game_port_adapter_with_oracle_query_log():
    """Ensure pure PublicGamePort adapter without _oracle / oracle attributes
    captures all 104 SAT calls (including 24 engine recheck queries) when passed
    a shared oracle_query_log channel."""
    puzzle = load_puzzle(str(ROOT / "puzzles/3x3/tutorial_3x3.json"))
    real_calls = 0

    def counting_solver(cnf: CNF, assumptions: tuple[int, ...] = ()) -> SATResult:
        nonlocal real_calls
        real_calls += 1
        return brute_force_test_solver(cnf, assumptions)

    shared_query_log: list[SATQuery] = []
    oracle = AgentVerdictOracle(encode_kb, counting_solver, query_log=shared_query_log)
    session = GameSession(puzzle, oracle)

    class PurePublicGamePortAdapter:
        """Strict adapter implementing PublicGamePort with only snapshot and submit_verdict."""
        __slots__ = ("_session",)

        def __init__(self, sess: GameSession):
            self._session = sess

        def snapshot(self) -> PublicState:
            return self._session.snapshot()

        def submit_verdict(self, cell: CellId, status: Status) -> SubmitResult:
            return self._session.submit_verdict(cell, status)

    adapter = PurePublicGamePortAdapter(session)
    assert not hasattr(adapter, "_oracle")
    assert not hasattr(adapter, "oracle")

    trace = auto_solve(
        adapter,
        encode_kb,
        counting_solver,
        oracle_query_log=shared_query_log,
    )
    assert trace.terminal == TraceStatus.SOLVED
    assert trace.deduction_steps == 8
    assert trace.total_sat_calls == real_calls == 104
    assert len(shared_query_log) == 24  # 8 steps x 3 verification queries (1 BASE_KB + 2 VERDICT_RECHECK)


def test_auto_solve_handles_immutable_or_custom_oracle_without_attribute_error():
    """Verify that an oracle without query_log that rejects attribute setting doesn't raise AttributeError."""
    class CustomVerdictOracle:
        __slots__ = ()

        def classify_one(self, state: PublicState, cell: CellId) -> Inference:
            return Inference.UNKNOWN

    fake_port = make_chain_2x2_game()

    class PureGamePort:
        __slots__ = ("_oracle", "_fake")

        def __init__(self, o, f):
            self._oracle = o
            self._fake = f

        def snapshot(self) -> PublicState:
            return self._fake.snapshot()

        def submit_verdict(self, cell: CellId, status: Status) -> SubmitResult:
            return self._fake.submit_verdict(cell, status)

    port = PureGamePort(CustomVerdictOracle(), fake_port)
    # Should run and complete SOLVED without raising AttributeError on _oracle.query_log
    trace = auto_solve(port, encode_kb, brute_force_test_solver)
    assert trace.terminal == TraceStatus.SOLVED
