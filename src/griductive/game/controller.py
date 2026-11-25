"""Controller for loading, proving one move, submitting a verdict and restarting."""

from dataclasses import dataclass
from pathlib import Path

from griductive.agent import (
    AgentVerdictOracle, DeductionTrace, KnowledgeBase, SATQuery, auto_solve, build_kb,
    classify_kb, select_forced_verdict,
)
from griductive.logic import encode_kb
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

    def __init__(self) -> None:
        self._session: GameSession | None = None
        self._recheck_queries: list[SATQuery] = []
        self.last_trace: VerdictTrace | None = None

    def _current(self) -> GameSession:
        if self._session is None:
            raise RuntimeError('Load a puzzle first')
        return self._session

    def load(self, path: str | Path) -> PublicState:
        puzzle = load_puzzle(str(path))
        oracle = AgentVerdictOracle(encode_kb, solve, query_log=self._recheck_queries)
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
        self.last_trace = None
        self._recheck_queries.clear()
        return auto_solve(self._current(), encode_kb, solve, oracle_query_log=self._recheck_queries)

    def step(self) -> SubmitResult:
        """Prove and submit at most one row-major forced verdict."""
        state = self.snapshot()
        if all(card.revealed for card in state.cards):
            return SubmitResult(VerdictStatus.NOT_PROVABLE, state, None, 'Puzzle already solved')
        self.last_trace = None
        kb = build_kb(state, encode_kb)
        queries: list[SATQuery] = []
        inferences = classify_kb(kb, solve, query_log=queries)
        if Inference.INCONSISTENT in inferences.values():
            return SubmitResult(VerdictStatus.INCONSISTENT, state, None, 'Public clues contradict each other')
        forced = select_forced_verdict(state, inferences)
        if forced is None:
            return SubmitResult(VerdictStatus.NOT_PROVABLE, state, None, 'No forced move')
        cell, status = forced
        return self._submit(cell, status, kb, tuple(queries))

    def submit_verdict(self, cell: CellId, status: Status) -> SubmitResult:
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
