"""Controller for loading, proving one move, submitting a verdict and restarting."""

from dataclasses import dataclass
from pathlib import Path
from math import isfinite
from time import perf_counter

from griductive.agent import (
    AgentVerdictOracle, DeductionTrace, KnowledgeBase, SATQuery, auto_solve, build_kb,
    classify_kb, select_forced_verdict,
)
from griductive.logic import encode_kb
from griductive.agent.hint import get_hint
from griductive.models import SolverTimeout
from griductive.models import CNF, CellId, Inference, PublicState, Status, SubmitResult, VerdictStatus
from griductive.sat import solve

from .engine import GameSession, load_puzzle


@dataclass(frozen=True)
class VerdictTrace:
    cell: CellId
    verdict: Status
    outcome: VerdictStatus
    cnf: CNF
    active_clue_ids: tuple[str, ...]
    queries: tuple[SATQuery, ...]
    newly_revealed_clue_id: str | None


class Controller:
    """Own a session and expose only public results to the view."""

    def __init__(self, *, solve_timeout_s: float = 10.0) -> None:
        if not isfinite(solve_timeout_s) or solve_timeout_s < 0:
            raise ValueError('Proof time limit must be finite and non-negative')
        self._timeout_s = solve_timeout_s
        self._deadline = 0.0
        self._session: GameSession | None = None
        self._recheck_queries: list[SATQuery] = []
        self.last_trace: VerdictTrace | None = None

    def _begin_operation(self) -> None:
        self._deadline = perf_counter() + self._timeout_s

    def _solve(self, cnf, assumptions=()):
        remaining = self._deadline - perf_counter()
        if remaining <= 0:
            raise SolverTimeout('Proof time limit exceeded')
        result = solve(cnf, assumptions, timeout_s=remaining)
        if perf_counter() > self._deadline:
            raise SolverTimeout('Proof time limit exceeded')
        return result

    def fork(self) -> 'Controller':
        game = Controller(solve_timeout_s=self._timeout_s)
        oracle = AgentVerdictOracle(encode_kb, game._solve, query_log=game._recheck_queries)
        game._session = self._current().fork(oracle)
        game.last_trace = self.last_trace
        return game

    def get_hint(self):
        self._begin_operation()
        return get_hint(self.snapshot(), encode_kb, self._solve)

    def _current(self) -> GameSession:
        if self._session is None:
            raise RuntimeError('Load a puzzle first')
        return self._session

    def load(self, path: str | Path) -> PublicState:
        puzzle = load_puzzle(str(path))
        oracle = AgentVerdictOracle(encode_kb, self._solve, query_log=self._recheck_queries)
        self._session = GameSession(puzzle, oracle)
        self.last_trace = None
        return self.snapshot()

    def snapshot(self) -> PublicState:
        return self._current().snapshot()

    def restart(self) -> PublicState:
        state = self._current().restart()
        self.last_trace = None
        return state

    def auto_solve(self) -> DeductionTrace:
        self._begin_operation()
        self.last_trace = None
        self._recheck_queries.clear()
        return auto_solve(self._current(), encode_kb, self._solve, oracle_query_log=self._recheck_queries)

    def step(self) -> SubmitResult:
        """Prove and submit at most one row-major forced verdict."""
        self._begin_operation()
        state = self.snapshot()
        if all(card.revealed for card in state.cards):
            return SubmitResult(VerdictStatus.NOT_PROVABLE, state, None, 'Puzzle already solved')
        self.last_trace = None
        kb = build_kb(state, encode_kb)
        queries: list[SATQuery] = []
        inferences = classify_kb(kb, self._solve, query_log=queries)
        if Inference.INCONSISTENT in inferences.values():
            return SubmitResult(VerdictStatus.INCONSISTENT, state, None, 'Public clues contradict each other')
        forced = select_forced_verdict(state, inferences)
        if forced is None:
            return SubmitResult(VerdictStatus.NOT_PROVABLE, state, None, 'No forced move')
        cell, status = forced
        return self._submit(cell, status, kb, tuple(queries))

    def submit_verdict(self, cell: CellId, status: Status) -> SubmitResult:
        self._begin_operation()
        self.last_trace = None
        kb = build_kb(self.snapshot(), encode_kb)
        return self._submit(cell, status, kb)

    def _submit(
        self, cell: CellId, status: Status, kb: KnowledgeBase, proof_queries: tuple[SATQuery, ...] = (),
    ) -> SubmitResult:
        self._recheck_queries.clear()
        result = self._current().submit_verdict(cell, status)
        clue_id = next(
            (card.clue.id for card in result.state.cards
             if card.cell == result.newly_revealed and card.clue is not None),
            None,
        )
        self.last_trace = VerdictTrace(
            cell, status, result.outcome, kb.cnf, kb.active_clue_ids,
            proof_queries + tuple(self._recheck_queries), clue_id,
        )
        return result
