"""Session state and proof-gated reveals. Hidden data never reaches the oracle."""
from griductive.models import (Clue, Inference, PublicCard, PublicState, Status,
                              SubmitResult, VerdictOracle, VerdictStatus)
from .loader import Puzzle


class PuzzleIntegrityError(ValueError):
    """An oracle-proved verdict disagrees with the puzzle's hidden solution."""


class GameSession:
    def __init__(self, puzzle: Puzzle, oracle: VerdictOracle):
        self._puzzle = puzzle
        self._oracle = oracle
        self._revealed = set(puzzle.initial_revealed)

    def snapshot(self) -> PublicState:
        cards = []
        for card in self._puzzle.cards:
            shown = card.cell in self._revealed
            clue = Clue(card.clue.id, card.clue.kind, card.clue.data) if shown else None
            cards.append(PublicCard(card.cell, card.name, card.profession, shown,
                                    card.hidden_status if shown else None, clue))
        return PublicState(self._puzzle.id, self._puzzle.size, tuple(cards))

    def restart(self) -> PublicState:
        self._revealed = set(self._puzzle.initial_revealed)
        return self.snapshot()

    def submit_verdict(self, cell: str, status: Status) -> SubmitResult:
        # Invalid/repeated requests are programmer errors and leave state intact.
        card = next((c for c in self._puzzle.cards if c.cell == cell), None)
        if card is None or cell in self._revealed:
            raise ValueError('Cell is invalid or already revealed')
        if not isinstance(status, Status):
            raise ValueError('Verdict must be a Status')
        state = self.snapshot()
        inference = self._oracle.classify_one(state, cell)
        if not isinstance(inference, Inference):
            raise TypeError('Oracle must return Inference')
        if inference == Inference.UNKNOWN:
            return SubmitResult(VerdictStatus.NOT_PROVABLE, state, None)
        if inference == Inference.INCONSISTENT:
            return SubmitResult(VerdictStatus.INCONSISTENT, state, None)
        if inference.value != status.value:
            return SubmitResult(VerdictStatus.CONTRADICTED, state, None)
        if card.hidden_status != status:
            raise PuzzleIntegrityError('Proved verdict conflicts with hidden solution')
        self._revealed.add(cell)
        return SubmitResult(VerdictStatus.ACCEPTED, self.snapshot(), cell)
