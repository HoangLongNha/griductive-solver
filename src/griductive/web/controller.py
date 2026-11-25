"""Translate the real Controller's public results into the React API payloads."""

from dataclasses import asdict
from copy import copy
import json
from pathlib import Path

from griductive.agent.hint import HintOutcome
from griductive.game.controller import Controller
from griductive.game.engine import PuzzleValidationError, load_puzzle
from griductive.logic import referenced_cells
from griductive.models import PublicState, Status, SubmitResult

from .clue_formatter import format_clue_text


class WebController:
    def __init__(self, puzzles_dir: Path, *, solve_timeout_s: float = 10.0) -> None:
        self._game = Controller(solve_timeout_s=solve_timeout_s)
        self._trace: list[dict] = []
        self._puzzles: dict[str, tuple[Path, dict]] = {}
        for path in sorted(puzzles_dir.rglob('*.json')):
            relative = path.relative_to(puzzles_dir)
            try:
                if relative.parts[0] == 'negative':
                    load_puzzle(str(path))  # Only offer diagnostics accepted by the game loader.
                metadata = json.loads(path.read_text(encoding='utf-8'))
                puzzle_id, size = metadata['id'], metadata['size']
                if not isinstance(puzzle_id, str) or type(size) is not int:
                    continue
            except (OSError, ValueError, KeyError, TypeError):
                continue
            category = relative.parts[0] if len(relative.parts) > 1 else 'default'
            if category == 'negative':
                category = 'diagnostic'
            self._puzzles[puzzle_id] = (path, {
                'id': puzzle_id, 'size': size, 'category': category, 'path': relative.as_posix(),
            })
        default = 'tutorial_3x3' if 'tutorial_3x3' in self._puzzles else next(iter(self._puzzles), None)
        if default is not None:
            self.load_puzzle(default)

    def list_puzzles(self) -> list[dict]:
        return [metadata for _, metadata in self._puzzles.values()]

    def fork(self) -> 'WebController':
        view = copy(self)
        view._game = self._game.fork()
        view._trace = list(self._trace)
        return view

    def load_puzzle(self, puzzle_id: str) -> dict:
        if puzzle_id not in self._puzzles:
            raise FileNotFoundError('Puzzle not found')
        try:
            state = self._game.load(self._puzzles[puzzle_id][0])
        except PuzzleValidationError:
            raise ValueError('Puzzle failed validation') from None
        self._trace.clear()
        return self._public_payload(state)

    def restart(self) -> dict:
        state = self._game.restart()
        self._trace.clear()
        return self._public_payload(state)

    def get_public_state_dict(self) -> dict:
        return self._public_payload(self._game.snapshot())

    def _public_payload(self, state: PublicState) -> dict:
        names = {card.cell: card.name for card in state.cards}
        cards = []
        for card in state.cards:
            clue = card.clue if card.revealed else None
            shown_clue = None if clue is None else {
                'id': clue.id, 'kind': clue.kind,
                'text': format_clue_text({**clue.data, 'kind': clue.kind}, names),
                'highlighted_cells': referenced_cells(clue, state.size),
            }
            cards.append({
                'cell': card.cell, 'name': card.name, 'profession': card.profession,
                'revealed': card.revealed, 'clue': shown_clue,
                'known_status': card.known_status.value if card.revealed and card.known_status else None,
            })
        revealed = sum(card.revealed for card in state.cards)
        return {'puzzle_id': state.puzzle_id, 'size': state.size, 'cards': cards,
                'revealed_count': revealed, 'total_count': len(cards),
                'solved': revealed == len(cards), 'trace': list(self._trace)}

    def _append_step(self, cell, verdict, clue_id, active_clues, queries) -> None:
        self._trace.append({
            'step': len(self._trace) + 1, 'cell': cell, 'verdict': verdict.value,
            'newly_revealed_clue': clue_id, 'active_clues': active_clues,
            'queries': [asdict(query) for query in queries],
        })

    def _verdict_payload(self, result: SubmitResult, *, include_proof: bool = True) -> dict:
        trace = self._game.last_trace if include_proof else None
        if result.newly_revealed is not None and trace is not None:
            self._append_step(trace.cell, trace.verdict, trace.newly_revealed_clue_id,
                              trace.active_clue_ids, trace.queries)
        message = result.message
        if not message and trace is not None:
            message = f'{trace.cell}: {trace.verdict.value} ({len(trace.queries)} SAT queries)'
        return {'outcome': result.outcome.value, 'newly_revealed': result.newly_revealed,
                'message': message, 'proof': asdict(trace) if trace else None,
                'state': self._public_payload(result.state)}

    def submit_verdict(self, cell: str, status: str) -> dict:
        return self._verdict_payload(self._game.submit_verdict(cell, Status(status)))

    def step(self) -> dict:
        already_solved = all(card.revealed for card in self._game.snapshot().cards)
        return self._verdict_payload(self._game.step(), include_proof=not already_solved)

    def get_hint(self) -> dict:
        state = self._game.snapshot()
        hint = self._game.get_hint()
        source = next((card for card in state.cards if card.clue and hint.cell in
                       referenced_cells(card.clue, state.size)), None)
        status = {HintOutcome.FORCED: 'FOUND', HintOutcome.INCONSISTENT: 'INCONSISTENT'}.get(
            hint.outcome, 'NONE')
        return {'status': status, 'cell': hint.cell, 'message': hint.message,
                'suggested_verdict': hint.status.value if hint.status else None,
                'relevant_clue_cell': source.cell if source else None,
                'highlighted_cells': referenced_cells(source.clue, state.size) if source else (
                    (hint.cell,) if hint.cell else ())}

    def auto_solve(self) -> dict:
        start = len(self._trace)
        trace = self._game.auto_solve()
        for step in trace.steps:
            self._append_step(step.cell, step.verdict, step.newly_revealed_clue_id,
                              step.active_clue_ids, step.queries)
        return {'terminal_status': trace.status.value, 'steps_added': self._trace[start:],
                'state': self._public_payload(trace.final_state)}
