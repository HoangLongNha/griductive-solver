"""Acceptance and integration tests for Task 4.4: Agent integration, negative tests & report.

Test IDs:
- AGI-01: End-to-end integration with real modules (GameSession + encode_kb + dpll.solve).
          Solves tutorial_3x3, extensions_3x3, chain_4x4_a, chain_4x4_b to TraceStatus.SOLVED.
- AGI-02: Negative test - Ambiguous public state (ambiguous_3x3.json).
          Stops at TraceStatus.STUCK with 0 reveals; get_hint returns NO_FORCED_MOVE.
- AGI-03: Negative test - Inconsistent public state (inconsistent_public_3x3.json).
          Terminates safely at TraceStatus.INCONSISTENT with 0 reveals; get_hint returns INCONSISTENT.
- Validation Uniqueness: check_unique_complete and analyze_unique_complete with real DPLL solver.
- Timeout / Error propagation: SolverTimeout propagates without false UNSAT or guessing.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from griductive.agent import (
    AgentVerdictOracle,
    HintOutcome,
    SATQuery,
    TraceStatus,
    aggregate_queries,
    auto_solve,
    classify,
    get_hint,
)
from griductive.game.engine import GameSession, PuzzleValidationError, load_puzzle
from griductive.logic.encoder import encode_full_clues, encode_kb
from griductive.models import (
    CNF,
    Clue,
    Inference,
    PublicCard,
    PublicState,
    SolverTimeout,
    Status,
    VerdictStatus,
)
from griductive.sat.dpll import solve
from griductive.validation.uniqueness import (
    UniquenessStatus,
    analyze_unique_cnf,
    analyze_unique_complete,
    check_unique_complete,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PUZZLES_DIR = REPO_ROOT / "puzzles"


# ==============================================================================
# Helper fixtures / utilities
# ==============================================================================

def _load_inconsistent_public_state() -> PublicState:
    """Construct an inconsistent PublicState from puzzles/negative/inconsistent_public_3x3.json.

    The fixture cannot be loaded via `load_puzzle` because VT1's loader validates
    that puzzle clues agree with hidden solution. We build the public snapshot directly
    to simulate an inconsistent public knowledge state.
    """
    path = PUZZLES_DIR / "negative" / "inconsistent_public_3x3.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    revealed = set(data["initial_revealed"])
    cards = []
    for c in data["cards"]:
        shown = c["cell"] in revealed
        clue = Clue(c["clue"]["id"], c["clue"]["kind"], c["clue"]) if shown else None
        status = Status(c["hidden_status"]) if shown else None
        cards.append(PublicCard(c["cell"], c["name"], c["profession"], shown, status, clue))
    return PublicState(data["id"], data["size"], tuple(cards))


class CountingSolver:
    """Wrapper around real DPLL `solve` counting actual invocations."""

    def __init__(self, solver=solve):
        self._solver = solver
        self.call_count = 0

    def __call__(self, cnf: CNF, assumptions=(), timeout_s=None):
        self.call_count += 1
        return self._solver(cnf, assumptions, timeout_s=timeout_s)


# ==============================================================================
# AGI-01: End-to-end integration with real DPLL solver on playable fixtures
# ==============================================================================

@pytest.mark.parametrize(
    ("puzzle_relpath", "expected_steps", "expected_sat_calls"),
    [
        ("3x3/tutorial_3x3.json", 8, 104),
        ("3x3/extensions_3x3.json", 8, 104),
        ("4x4/chain_4x4_a.json", 15, 300),
        ("4x4/chain_4x4_b.json", 15, 300),
    ],
)
def test_agi01_full_solve_playable_puzzles_with_real_dpll(
    puzzle_relpath: str,
    expected_steps: int,
    expected_sat_calls: int,
):
    """AGI-01: Agent + GameSession + encode_kb + real DPLL solve end-to-end.

    Verifies:
    1. Terminal status is SOLVED.
    2. All N^2 cards on the board are revealed.
    3. Every step outcome is ACCEPTED with valid forced verdicts.
    4. Exact step count equals (total_cells - initial_revealed).
    5. Trace total_sat_calls matches real solver calls exactly (including Engine recheck queries).
    6. Aggregate metrics equal exact sum of all_queries.
    """
    puzzle_path = PUZZLES_DIR / puzzle_relpath
    puzzle = load_puzzle(puzzle_path)

    recheck_log: list[SATQuery] = []
    counting_solver = CountingSolver(solve)
    oracle = AgentVerdictOracle(encode_kb, counting_solver, query_log=recheck_log)
    session = GameSession(puzzle, oracle)

    trace = auto_solve(
        session,
        encode_kb,
        counting_solver,
        oracle_query_log=recheck_log,
    )

    # 1. Terminal state assertions
    assert trace.status == TraceStatus.SOLVED
    assert trace.puzzle_id == puzzle.id
    assert len(trace.steps) == expected_steps

    # 2. Board completion: every card is revealed and matches puzzle hidden status
    final_cards = trace.final_state.cards
    assert len(final_cards) == puzzle.size * puzzle.size
    assert all(c.revealed for c in final_cards)
    for c in final_cards:
        expected_status = next(p.hidden_status for p in puzzle.cards if p.cell == c.cell)
        assert c.known_status == expected_status

    # 3. Every step was accepted
    for step in trace.steps:
        assert step.outcome == VerdictStatus.ACCEPTED
        assert step.verdict in (Status.CRIMINAL, Status.INNOCENT)

    # 4. SAT Call count accounting (CONTRACTS §7)
    assert trace.total_sat_calls == expected_sat_calls
    assert counting_solver.call_count == expected_sat_calls
    assert len(trace.all_queries) == expected_sat_calls

    # 5. Aggregate statistics consistency
    aggregated = aggregate_queries(trace.all_queries)
    assert trace.totals.sat_calls == aggregated.sat_calls
    assert trace.totals.decisions == aggregated.decisions
    assert trace.totals.propagations == aggregated.propagations
    assert trace.totals.backtracks == aggregated.backtracks
    assert trace.totals.sat_runtime_s == pytest.approx(aggregated.sat_runtime_s, rel=1e-5)
    assert trace.total_runtime_s >= trace.totals.sat_runtime_s


def test_agi01_streaming_callback_and_audit_completeness():
    """Verify on_step callback receives valid DeductionStep records sequentially."""
    puzzle = load_puzzle(PUZZLES_DIR / "3x3" / "tutorial_3x3.json")
    recheck_log: list[SATQuery] = []
    oracle = AgentVerdictOracle(encode_kb, solve, query_log=recheck_log)
    session = GameSession(puzzle, oracle)

    streamed_steps = []

    def on_step(step):
        streamed_steps.append(step)

    trace = auto_solve(
        session,
        encode_kb,
        solve,
        on_step=on_step,
        oracle_query_log=recheck_log,
    )

    assert trace.status == TraceStatus.SOLVED
    assert len(streamed_steps) == 8
    for idx, step in enumerate(streamed_steps, start=1):
        assert step.step_index == idx
        assert step.step_number == idx
        assert step.outcome == VerdictStatus.ACCEPTED
        assert len(step.queries) > 0


# ==============================================================================
# AGI-02: Negative test - Ambiguous public state
# ==============================================================================

def test_agi02_ambiguous_puzzle_stops_stuck_with_zero_guesses():
    """AGI-02: Ambiguous public state stops cleanly at STUCK with 0 reveals.

    On puzzles/negative/ambiguous_3x3.json:
    - Initial revealed card provides clues that leave multiple candidates open.
    - Agent must NEVER guess: stops at TraceStatus.STUCK.
    - No cards are revealed during auto_solve.
    - get_hint returns HintOutcome.NO_FORCED_MOVE with cell=None.
    """
    puzzle = load_puzzle(PUZZLES_DIR / "negative" / "ambiguous_3x3.json")
    oracle = AgentVerdictOracle(encode_kb, solve)
    session = GameSession(puzzle, oracle)

    initial_revealed_count = sum(1 for c in session.snapshot().cards if c.revealed)

    trace = auto_solve(session, encode_kb, solve)

    assert trace.status == TraceStatus.STUCK
    assert len(trace.steps) == 0
    assert "No entailed verdict" in trace.message

    # No additional cards revealed
    after_revealed_count = sum(1 for c in session.snapshot().cards if c.revealed)
    assert after_revealed_count == initial_revealed_count

    # Public Hint check
    hint = get_hint(session.snapshot(), encode_kb, solve)
    assert hint.outcome == HintOutcome.NO_FORCED_MOVE
    assert hint.cell is None
    assert hint.status is None
    assert "forced" in hint.message.lower()


def test_agi02_ambiguous_puzzle_contrast_with_full_clue_uniqueness():
    """Contrast AGI-02: Ambiguous in public gameplay vs Unique in offline full-clue validation.

    `ambiguous_3x3.json` has a unique complete primary model when ALL clues are revealed,
    proving that `check_unique_complete == True`.
    However, the public game state with only initial clues does NOT admit any forced move,
    proving that our Agent correctly respects the information boundary.
    """
    puzzle = load_puzzle(PUZZLES_DIR / "negative" / "ambiguous_3x3.json")

    # Offline validation with all clues: Unique
    is_unique = check_unique_complete(puzzle, encode_full_clues, solve)
    assert is_unique is True

    # In-game public state: NO forced move
    oracle = AgentVerdictOracle(encode_kb, solve)
    session = GameSession(puzzle, oracle)
    hint = get_hint(session.snapshot(), encode_kb, solve)
    assert hint.outcome == HintOutcome.NO_FORCED_MOVE


# ==============================================================================
# AGI-03: Negative test - Inconsistent public state
# ==============================================================================

def test_agi03_inconsistent_puzzle_rejected_by_loader():
    """Verify that inconsistent_public_3x3.json is rejected by load_puzzle (puzzle validation)."""
    incon_path = PUZZLES_DIR / "negative" / "inconsistent_public_3x3.json"
    with pytest.raises(PuzzleValidationError, match="contradicts hidden solution"):
        load_puzzle(incon_path)


def test_agi03_inconsistent_public_state_stops_immediately_without_reveals():
    """AGI-03: Inconsistent public state detected at Base KB, yields INCONSISTENT with 0 reveals.

    Constructs a PublicState from inconsistent_public_3x3.json (clue says B1 is CRIMINAL,
    but B1's public status is INNOCENT).
    Verifies:
    1. `classify` returns Inference.INCONSISTENT for all unresolved cells.
    2. `auto_solve` stops immediately at TraceStatus.INCONSISTENT with 0 steps.
    3. `get_hint` returns HintOutcome.INCONSISTENT.
    """
    public = _load_inconsistent_public_state()

    # 1. Classification check
    inferences = classify(public, encode_kb, solve)
    assert len(inferences) > 0
    assert all(inf == Inference.INCONSISTENT for inf in inferences.values())

    # 2. auto_solve check with a dummy PublicGamePort
    class ImmutablePublicPort:
        def snapshot(self) -> PublicState:
            return public

        def submit_verdict(self, cell: str, status: Status):
            raise AssertionError("submit_verdict must not be called on inconsistent state")

    trace = auto_solve(ImmutablePublicPort(), encode_kb, solve)
    assert trace.status == TraceStatus.INCONSISTENT
    assert len(trace.steps) == 0
    assert "Public knowledge base is inconsistent" in trace.message

    # 3. get_hint check
    hint = get_hint(public, encode_kb, solve)
    assert hint.outcome == HintOutcome.INCONSISTENT
    assert hint.cell is None
    assert hint.status is None


# ==============================================================================
# Validation Uniqueness with real DPLL Solver
# ==============================================================================

@pytest.mark.parametrize(
    "puzzle_relpath",
    [
        "3x3/tutorial_3x3.json",
        "3x3/extensions_3x3.json",
        "4x4/chain_4x4_a.json",
        "4x4/chain_4x4_b.json",
    ],
)
def test_uniqueness_complete_on_playable_puzzles(puzzle_relpath: str):
    """Verify all playable puzzles admit a unique primary solution under real DPLL solve."""
    puzzle = load_puzzle(PUZZLES_DIR / puzzle_relpath)
    result = analyze_unique_complete(puzzle, encode_full_clues, solve)

    assert result.status == UniquenessStatus.UNIQUE
    assert result.is_unique is True
    assert result.first_model is not None
    assert result.second_model is None
    assert len(result.first_model) == puzzle.size * puzzle.size


def test_uniqueness_cnf_detects_multiple_models_with_real_dpll():
    """Verify check_unique_cnf identifies multiple models when under-constrained."""
    # Under-constrained: 2 variables, single clause (1 or 2) -> models: (1, 2), (1, -2), (-1, 2)
    cnf = CNF(clauses=((1, 2),), primary_count=2, variable_count=2)
    res = analyze_unique_cnf(cnf, solve)

    assert res.status == UniquenessStatus.MULTIPLE
    assert res.is_unique is False
    assert res.first_model is not None
    assert res.second_model is not None
    assert res.first_model != res.second_model


def test_primary_blocking_clause_isolates_primary_variables_under_real_dpll():
    """Verify blocking clause in second SAT call uses only primary variables 1..primary_count."""
    # 2 primary variables, 1 auxiliary variable
    # primary: 1, 2; aux: 3
    # cnf: (1 or 2) and (3 <-> 1) -> clauses: (1, 2), (-3, 1), (-1, 3)
    cnf = CNF(clauses=((1, 2), (-3, 1), (-1, 3)), primary_count=2, variable_count=3)
    queries = []

    res = analyze_unique_cnf(cnf, solve, query_log=queries)
    assert res.status == UniquenessStatus.MULTIPLE
    assert len(queries) == 2

    # Verify blocking clause is appended and contains only primary variables
    assert res.blocking_clause is not None
    assert len(res.blocking_clause) == 2  # exactly primary_count variables
    # Primary count is 2: all literals in blocking clause must be in {-2, -1, 1, 2}
    for lit in res.blocking_clause:
        assert 1 <= abs(lit) <= 2, f"Blocking literal {lit} exceeds primary count 2!"


# ==============================================================================
# Robustness & SolverTimeout handling
# ==============================================================================

def test_solver_timeout_propagation_in_integration_flow():
    """Verify that SolverTimeout is propagated cleanly through auto_solve and get_hint."""
    def timeout_solver(cnf: CNF, assumptions=(), timeout_s=None):
        raise SolverTimeout("Simulated DPLL budget exceeded")

    puzzle = load_puzzle(PUZZLES_DIR / "3x3" / "tutorial_3x3.json")
    oracle = AgentVerdictOracle(encode_kb, timeout_solver)
    session = GameSession(puzzle, oracle)

    with pytest.raises(SolverTimeout, match="Simulated DPLL budget exceeded"):
        auto_solve(session, encode_kb, timeout_solver)

    with pytest.raises(SolverTimeout, match="Simulated DPLL budget exceeded"):
        get_hint(session.snapshot(), encode_kb, timeout_solver)
