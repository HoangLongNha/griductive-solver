"""Acceptance and unit tests for Task 4.1: KB & entailment classification.

Test IDs: AG-01, AG-02, AG-03, AG-04, AG-05.
Uses injected FakeEncoder / FakeSolver (no DPLL dependency) plus cross-checks
with VT2's real `encode_kb` and VT1's `GameSession` boundary.
"""
from itertools import product
from pathlib import Path

import pytest

from griductive.agent import (
    AgentVerdictOracle,
    QueryPurpose,
    build_kb,
    classify,
    classify_kb,
    classify_one,
)
from griductive.game.engine import GameSession, load_puzzle
from griductive.logic import encode_kb
from griductive.models import (
    CNF,
    Clue,
    Inference,
    PublicCard,
    PublicState,
    SATResult,
    SATStats,
    SolverCancelled,
    SolverTimeout,
    Status,
    VerdictStatus,
    cell_to_var,
    var_to_cell,
)

ROOT = Path(__file__).resolve().parents[2]


def make_public_state(size: int = 3, revealed: dict[str, tuple[Status, Clue | None]] | None = None) -> PublicState:
    revealed = revealed or {}
    cards = []
    for var in range(1, size * size + 1):
        cell = var_to_cell(var, size)
        if cell in revealed:
            status, clue = revealed[cell]
            cards.append(PublicCard(cell, f"P{var}", "Citizen", True, status, clue))
        else:
            cards.append(PublicCard(cell, f"P{var}", "Citizen", False, None, None))
    return PublicState(puzzle_id=f"test_{size}x{size}", size=size, cards=tuple(cards))


class FakeEncoder:
    """Object-port fake encoder exposing `.encode_kb(public)`."""

    def __init__(self, extra_clauses: tuple[tuple[int, ...], ...] = (), aux_vars: int = 0):
        self.extra_clauses = extra_clauses
        self.aux_vars = aux_vars
        self.seen_states: list[PublicState] = []

    def encode_kb(self, public: PublicState) -> CNF:
        self.seen_states.append(public)
        clauses = []
        for card in public.cards:
            if not card.revealed:
                continue
            var = cell_to_var(card.cell, public.size)
            if card.known_status == Status.CRIMINAL:
                clauses.append((var,))
            elif card.known_status == Status.INNOCENT:
                clauses.append((-var,))
        clauses.extend(self.extra_clauses)
        primary = public.size * public.size
        return CNF(tuple(clauses), primary_count=primary, variable_count=primary + self.aux_vars)


class StubSolver:
    """Deterministic fake SAT solver controlled by explicit UNSAT assumption rules."""

    def __init__(self, unsat_assumptions: set[tuple[int, ...]] | None = None, kb_sat: bool = True):
        self.unsat_assumptions = unsat_assumptions or set()
        self.kb_sat = kb_sat
        self.calls: list[tuple[int, ...]] = []

    def solve(self, cnf: CNF, assumptions: tuple[int, ...] = ()) -> SATResult:
        self.calls.append(assumptions)
        stats = SATStats(decisions=1, propagations=2, backtracks=0, runtime_s=0.001)
        if not self.kb_sat or assumptions in self.unsat_assumptions:
            return SATResult(is_sat=False, assignment=None, stats=stats)
        return SATResult(
            is_sat=True,
            assignment={v: True for v in range(1, cnf.variable_count + 1)},
            stats=stats,
        )


def brute_force_test_solver(cnf: CNF, assumptions: tuple[int, ...] = ()) -> SATResult:
    """Test-only exhaustive SAT solver for small CNFs (NOT production DPLL)."""
    all_clauses = cnf.clauses + tuple((lit,) for lit in assumptions)
    stats = SATStats(decisions=1, propagations=0, backtracks=0, runtime_s=0.0005)
    for bits in product((False, True), repeat=cnf.variable_count):
        assignment = {v: bits[v - 1] for v in range(1, cnf.variable_count + 1)}
        if all(
            any(assignment[abs(lit)] if lit > 0 else not assignment[abs(lit)] for lit in clause)
            for clause in all_clauses
        ):
            return SATResult(is_sat=True, assignment=assignment, stats=stats)
    return SATResult(is_sat=False, assignment=None, stats=stats)


# =====================================================================
# Acceptance tests: AG-01 .. AG-05
# =====================================================================


def test_ag01_criminal_entailment():
    """AG-01: KB SAT & KB ∧ ¬Ci UNSAT -> CRIMINAL."""
    state = make_public_state(3, {"A1": (Status.CRIMINAL, None)})
    encoder = FakeEncoder()
    # B1 = var 2; KB ∧ (-2) is UNSAT => B1 is entailed CRIMINAL
    solver = StubSolver(unsat_assumptions={(-2,)})

    result = classify(state, encoder, solver)
    assert result["B1"] == Inference.CRIMINAL
    assert "A1" not in result  # Already revealed cells are excluded
    assert len(result) == 8


def test_ag02_innocent_entailment():
    """AG-02: KB SAT & KB ∧ Ci UNSAT -> INNOCENT."""
    state = make_public_state(3, {"A1": (Status.CRIMINAL, None)})
    encoder = FakeEncoder()
    # C1 = var 3; KB ∧ (+3) is UNSAT => C1 is entailed INNOCENT
    solver = StubSolver(unsat_assumptions={(3,)})

    result = classify(state, encoder, solver)
    assert result["C1"] == Inference.INNOCENT


def test_ag03_unknown_when_both_assumptions_sat():
    """AG-03: Both KB ∧ (-Ci) and KB ∧ (+Ci) SAT -> UNKNOWN."""
    state = make_public_state(3, {"A1": (Status.INNOCENT, None)})
    encoder = FakeEncoder()
    solver = StubSolver()

    result = classify(state, encoder, solver)
    assert len(result) == 8
    assert all(inf == Inference.UNKNOWN for inf in result.values())


def test_ag04_inconsistent_kb_returns_inconsistent_without_cell_queries():
    """AG-04: KB UNSAT -> INCONSISTENT for every unresolved cell; no per-cell verdict queries."""
    state = make_public_state(3, {"A1": (Status.CRIMINAL, None)})
    encoder = FakeEncoder()
    solver = StubSolver(kb_sat=False)

    result = classify(state, encoder, solver)
    assert len(result) == 8
    assert all(inf == Inference.INCONSISTENT for inf in result.values())
    # Only the base KB check () should have been issued
    assert solver.calls == [()]


def test_ag05_privacy_boundary_rejects_puzzle_and_only_uses_public_clues():
    """AG-05: Agent accepts PublicState only and never reads face-down cards or hidden clues."""
    puzzle = load_puzzle(str(ROOT / "puzzles/3x3/tutorial_3x3.json"))

    # Reject raw Puzzle object directly (privacy boundary enforcement)
    with pytest.raises(TypeError):
        build_kb(puzzle, encode_kb)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        classify(puzzle, encode_kb, brute_force_test_solver)  # type: ignore[arg-type]

    # With GameSession snapshot on tutorial_3x3:
    # A1 is initially revealed with clue FACT(B1=INNOCENT); B1's hidden clue SAME(B1, C1) must NOT be used yet!
    game = GameSession(puzzle, AgentVerdictOracle(encode_kb, brute_force_test_solver))
    snapshot = game.snapshot()
    kb = build_kb(snapshot, encode_kb)

    assert kb.active_clue_ids == ("c-A1",)
    assert kb.revealed_cells == frozenset({"A1"})
    assert "B1" in kb.unresolved_cells
    assert "C1" in kb.unresolved_cells

    inferences = classify(snapshot, encode_kb, brute_force_test_solver)
    assert inferences["B1"] == Inference.INNOCENT
    # C1 depends on B1's hidden clue, so C1 MUST still be UNKNOWN
    assert inferences["C1"] == Inference.UNKNOWN


def test_ag05_two_private_puzzles_with_same_public_state_give_identical_result():
    """AG-05 (Notion v0.2 Privacy): two puzzles with different hidden statuses/clues
    but identical PublicState produce identical encoder input and identical inference."""
    from griductive.game.loader import PrivateCard, Puzzle

    shared_a1 = PrivateCard(
        "A1", "Alice", "Chef", Status.CRIMINAL, Clue("c-A1", "FACT", {"cell": "B1", "status": "INNOCENT"})
    )
    puzzle_1 = Puzzle(
        id="priv_check",
        size=2,
        initial_revealed=("A1",),
        cards=(
            shared_a1,
            PrivateCard("B1", "Bob", "Guard", Status.INNOCENT, Clue("c-B1-p1", "FACT", {"cell": "A2", "status": "CRIMINAL"})),
            PrivateCard("A2", "Cara", "Nurse", Status.CRIMINAL, Clue("c-A2-p1", "FACT", {"cell": "B2", "status": "CRIMINAL"})),
            PrivateCard("B2", "Dan", "Pilot", Status.CRIMINAL, Clue("c-B2-p1", "FACT", {"cell": "A1", "status": "CRIMINAL"})),
        ),
    )
    puzzle_2 = Puzzle(
        id="priv_check",
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
    snap_1 = GameSession(puzzle_1, oracle).snapshot()
    snap_2 = GameSession(puzzle_2, oracle).snapshot()

    recorded_inputs: list[PublicState] = []

    def spy_encoder(public: PublicState) -> CNF:
        recorded_inputs.append(public)
        return encode_kb(public)

    res_1 = classify(snap_1, spy_encoder, brute_force_test_solver)
    res_2 = classify(snap_2, spy_encoder, brute_force_test_solver)

    assert recorded_inputs[0] == recorded_inputs[1]
    assert res_1 == res_2 == {
        "B1": Inference.INNOCENT,
        "A2": Inference.UNKNOWN,
        "B2": Inference.UNKNOWN,
    }


# =====================================================================
# Contract & edge-case tests
# =====================================================================


def test_kb_row_major_ordering_and_cnf_metrics():
    """KB normalizes unresolved_cells & active_clue_ids to row-major order and reports CNF counts."""
    clue_a1 = Clue("c-A1", "FACT", {"cell": "B1", "status": "INNOCENT"})
    clue_a2 = Clue("c-A2", "FACT", {"cell": "B2", "status": "CRIMINAL"})
    normal_state = make_public_state(
        3,
        {"A1": (Status.CRIMINAL, clue_a1), "A2": (Status.INNOCENT, clue_a2)},
    )
    # Reverse card order to verify KB still sorts deterministically row-major
    shuffled = PublicState(normal_state.puzzle_id, normal_state.size, tuple(reversed(normal_state.cards)))
    encoder = FakeEncoder(extra_clauses=((-1, 2),), aux_vars=2)

    kb = build_kb(shuffled, encoder)
    assert kb.active_clue_ids == ("c-A1", "c-A2")
    assert kb.unresolved_cells == ("B1", "C1", "B2", "C2", "A3", "B3", "C3")
    assert kb.metrics.primary_count == 9
    assert kb.metrics.aux_count == 2
    assert kb.metrics.clause_count == 3


def test_query_log_records_purposes_and_assumptions():
    """SATQuery audit log records BASE_KB and CLASSIFY calls with exact assumptions."""
    state = make_public_state(2, {"A1": (Status.CRIMINAL, None)})
    encoder = FakeEncoder(extra_clauses=((-1, 2),))  # A1 -> B1 (so B1 is CRIMINAL)
    kb = build_kb(state, encoder)
    log = []

    result = classify_kb(kb, brute_force_test_solver, query_log=log)
    assert result == {
        "B1": Inference.CRIMINAL,
        "A2": Inference.UNKNOWN,
        "B2": Inference.UNKNOWN,
    }
    assert log[0].purpose == QueryPurpose.BASE_KB
    assert log[0].assumptions == ()
    assert log[0].is_sat is True

    # 1 base call + 2 assumption calls for each of the 3 unresolved cells = 7 queries
    assert len(log) == 7
    b1_queries = [q for q in log if q.target_cell == "B1"]
    assert [(q.purpose, q.assumptions, q.is_sat) for q in b1_queries] == [
        (QueryPurpose.CLASSIFY, (-2,), False),
        (QueryPurpose.CLASSIFY, (2,), True),
    ]


def test_solver_timeout_and_cancelled_propagate_never_unsat():
    """Unfinished queries (SolverTimeout / SolverCancelled) must propagate and never become verdicts."""
    state = make_public_state(2, {"A1": (Status.CRIMINAL, None)})
    encoder = FakeEncoder()

    def timeout_solver(cnf, assumptions=()):
        raise SolverTimeout("time limit exceeded")

    def cancelled_solver(cnf, assumptions=()):
        raise SolverCancelled("cancelled by user")

    with pytest.raises(SolverTimeout):
        classify(state, encoder, timeout_solver)
    with pytest.raises(SolverCancelled):
        classify(state, encoder, cancelled_solver)


def test_agent_verdict_oracle_integrates_with_game_session():
    """AgentVerdictOracle satisfies GameSession's VerdictOracle and tags VERDICT_RECHECK calls."""
    puzzle = load_puzzle(str(ROOT / "puzzles/3x3/tutorial_3x3.json"))
    recheck_log = []
    oracle = AgentVerdictOracle(encode_kb, brute_force_test_solver, query_log=recheck_log)
    game = GameSession(puzzle, oracle)

    # Unprovable cell C1 must be rejected as NOT_PROVABLE
    rejected = game.submit_verdict("C1", Status.INNOCENT)
    assert rejected.outcome == VerdictStatus.NOT_PROVABLE
    assert rejected.newly_revealed is None

    # Opposite of entailed B1 (INNOCENT) must be CONTRADICTED
    wrong = game.submit_verdict("B1", Status.CRIMINAL)
    assert wrong.outcome == VerdictStatus.CONTRADICTED
    assert wrong.newly_revealed is None

    # Correct entailed verdict for B1 must be ACCEPTED and reveal B1
    accepted = game.submit_verdict("B1", Status.INNOCENT)
    assert accepted.outcome == VerdictStatus.ACCEPTED
    assert accepted.newly_revealed == "B1"

    # All cell-level queries from the oracle carry VERDICT_RECHECK
    cell_queries = [q for q in recheck_log if q.target_cell is not None]
    assert cell_queries
    assert all(q.purpose == QueryPurpose.VERDICT_RECHECK for q in cell_queries)


def test_classify_one_and_empty_unresolved_board():
    """classify_one checks a single cell; a fully revealed board yields an empty classification dict."""
    full_state = make_public_state(
        2,
        {
            "A1": (Status.CRIMINAL, None),
            "B1": (Status.INNOCENT, None),
            "A2": (Status.INNOCENT, None),
            "B2": (Status.CRIMINAL, None),
        },
    )
    assert classify(full_state, FakeEncoder(), StubSolver()) == {}

    partial = make_public_state(2, {"A1": (Status.CRIMINAL, None)})
    assert classify_one(partial, "B1", FakeEncoder(), StubSolver(unsat_assumptions={(-2,)})) == Inference.CRIMINAL
    with pytest.raises(ValueError):
        classify_one(partial, "Z9", FakeEncoder(), StubSolver())
