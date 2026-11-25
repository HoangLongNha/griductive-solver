"""FakeController and MockGameSession for React UI development (Task 5.1 / 5.2).

Respects CONTRACTS.md privacy boundary:
- Hidden statuses and unrevealed clues stay inside _MockGameSession.
- Only PublicState projections are exposed to the web server / React UI.
"""
from __future__ import annotations

from .clue_formatter import format_clue_text

import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from griductive.models import (
    CellId,
    Clue,
    Inference,
    PublicCard,
    PublicState,
    SATStats,
    Status,
    SubmitResult,
    VerdictStatus,
)


def resolve_region_cells(region: dict[str, Any], size: int) -> list[CellId]:
    """Resolve a structured region dict into row-major CellIds."""
    rtype = region.get("type")
    if rtype == "row":
        row = int(region["index"])
        return [f"{chr(ord('A') + c)}{row}" for c in range(size)]
    if rtype == "column":
        col = str(region["index"])
        return [f"{col}{r}" for r in range(1, size + 1)]
    if rtype == "neighbors":
        center = str(region["cell"])
        col = ord(center[0]) - ord("A")
        row = int(center[1:]) - 1
        cells: list[CellId] = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = row + dr, col + dc
                if 0 <= nr < size and 0 <= nc < size:
                    cells.append(f"{chr(ord('A') + nc)}{nr + 1}")
        return sorted(cells, key=lambda cid: (int(cid[1:]), cid[0]))
    if rtype == "cells":
        return list(region.get("cells", []))
    return []


def extract_referenced_cells(clue: dict[str, Any], size: int) -> list[CellId]:
    """Return all cells referenced or counted by a clue for UI highlighting."""
    kind = clue.get("kind")
    if kind == "FACT":
        return [str(clue["cell"])]
    if kind in ("SAME", "DIFFERENT"):
        return [str(c) for c in clue.get("cells", [])]
    if kind in ("EXACTLY", "AT_LEAST", "AT_MOST", "PARITY"):
        return resolve_region_cells(clue.get("region", {}), size)
    if kind == "COMPOUND":
        seen: list[CellId] = []
        for item in clue.get("premises", []):
            cid = str(item["cell"])
            if cid not in seen:
                seen.append(cid)
        concl = clue.get("conclusion", {})
        if "cell" in concl and str(concl["cell"]) not in seen:
            seen.append(str(concl["cell"]))
        return seen
    return []


def _evaluate_clue_dict(clue: dict[str, Any], assignment: dict[CellId, bool], size: int) -> bool:
    """Semantic evaluator used ONLY by the mock UI oracle for small boards."""
    kind = clue["kind"]
    if kind == "FACT":
        want = clue["status"] == "CRIMINAL"
        return assignment[clue["cell"]] is want
    if kind == "SAME":
        a, b = clue["cells"]
        return assignment[a] == assignment[b]
    if kind == "DIFFERENT":
        a, b = clue["cells"]
        return assignment[a] != assignment[b]
    if kind in ("EXACTLY", "AT_LEAST", "AT_MOST", "PARITY"):
        cells = resolve_region_cells(clue["region"], size)
        count = sum(1 for c in cells if assignment[c])
        if kind == "EXACTLY":
            return count == int(clue["k"])
        if kind == "AT_LEAST":
            return count >= int(clue["k"])
        if kind == "AT_MOST":
            return count <= int(clue["k"])
        want_odd = clue["parity"] == "ODD"
        return (count % 2 == 1) == want_odd
    if kind == "COMPOUND":
        prem_ok = all(
            assignment[p["cell"]] is (p["status"] == "CRIMINAL")
            for p in clue.get("premises", [])
        )
        if not prem_ok:
            return True
        c = clue["conclusion"]
        return assignment[c["cell"]] is (c["status"] == "CRIMINAL")
    raise ValueError(f"Unsupported clue kind: {kind}")


class _MockVerdictOracle:
    """Mock VerdictOracle operating strictly on PublicState.

    For small boards (<= 4x4), checks logical entailment over public clues/statuses
    so the React UI behaves identically to the real DPLL agent during UI development.
    """

    def classify_all(self, state: PublicState) -> dict[CellId, Inference]:
        cells = [card.cell for card in state.cards]
        revealed_clues = [card.clue for card in state.cards if card.revealed and card.clue is not None]
        known = {
            card.cell: (card.known_status == Status.CRIMINAL)
            for card in state.cards
            if card.revealed and card.known_status is not None
        }
        unknown_cells = [c for c in cells if c not in known]

        if len(unknown_cells) > 16:
            # Fallback for 5x5 mock before real DPLL is plugged in:
            return {c: Inference.UNKNOWN for c in unknown_cells}

        models: list[dict[CellId, bool]] = []
        for bits in itertools.product((False, True), repeat=len(unknown_cells)):
            assign = dict(known)
            for cid, val in zip(unknown_cells, bits):
                assign[cid] = val
            if all(_evaluate_clue_dict(dict(clue.data), assign, state.size) for clue in revealed_clues):
                models.append(assign)

        if not models:
            return {c: Inference.INCONSISTENT for c in unknown_cells}

        result: dict[CellId, Inference] = {}
        for c in unknown_cells:
            vals = {m[c] for m in models}
            if vals == {True}:
                result[c] = Inference.CRIMINAL
            elif vals == {False}:
                result[c] = Inference.INNOCENT
            else:
                result[c] = Inference.UNKNOWN
        return result

    def classify_one(self, state: PublicState, cell: CellId) -> Inference:
        return self.classify_all(state).get(cell, Inference.UNKNOWN)


@dataclass
class PuzzleMeta:
    id: str
    category: str
    size: int
    path: str
    title: str


class FakeController:
    """Controller + MockGameSession backing the React UI endpoints."""

    def __init__(self, puzzles_dir: Path) -> None:
        self._puzzles_dir = puzzles_dir
        self._oracle = _MockVerdictOracle()
        self._raw_puzzle: dict[str, Any] = {}
        self._revealed: set[CellId] = set()
        self._deduction_steps: list[dict[str, Any]] = []
        self._step_counter = 0

        puzzles = self.list_puzzles()
        default_id = next((p["id"] for p in puzzles if p["id"] == "tutorial_3x3"), None)
        if default_id is None and puzzles:
            default_id = puzzles[0]["id"]
        if default_id is not None:
            self.load_puzzle(default_id)

    def list_puzzles(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self._puzzles_dir.rglob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            rel = path.relative_to(self._puzzles_dir)
            category = rel.parts[0] if len(rel.parts) > 1 else "default"
            items.append({
                "id": data.get("id", path.stem),
                "category": category,
                "size": int(data.get("size", 3)),
                "path": str(rel),
            })
        return items

    def load_puzzle(self, puzzle_id: str) -> dict[str, Any]:
        for path in sorted(self._puzzles_dir.rglob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("id") == puzzle_id or path.stem == puzzle_id:
                initial = self._validate_raw_puzzle(data)
                candidate_state = self._build_public_state(data, initial)
                payload = self._serialize_public_state(candidate_state, trace=[])
                self._raw_puzzle = data
                self._revealed = initial
                self._deduction_steps = []
                self._step_counter = 0
                return payload
        raise FileNotFoundError(f"Puzzle '{puzzle_id}' not found")

    def _validate_raw_puzzle(self, data: dict[str, Any]) -> set[CellId]:
        if not isinstance(data, dict):
            raise ValueError("Puzzle JSON must be an object")
        size = int(data["size"])
        _ = str(data["id"])
        raw_cards = data["cards"]
        if not isinstance(raw_cards, list) or len(raw_cards) != size * size:
            raise ValueError("Puzzle cards count does not match board size")
        cells: set[CellId] = set()
        for raw_card in raw_cards:
            cid = str(raw_card["cell"])
            _ = str(raw_card["name"])
            _ = str(raw_card["profession"])
            Status(raw_card["hidden_status"])
            clue = raw_card["clue"]
            _ = (str(clue["id"]), str(clue["kind"]))
            cells.add(cid)
        initial = set(data["initial_revealed"])
        if not initial or not initial <= cells:
            raise ValueError("initial_revealed must reference valid puzzle cells")
        return initial

    def restart(self) -> dict[str, Any]:
        self._revealed = set(self._raw_puzzle.get("initial_revealed", []))
        self._deduction_steps = []
        self._step_counter = 0
        return self.get_public_state_dict()

    def _build_public_state(
        self,
        raw_puzzle: dict[str, Any] | None = None,
        revealed: set[CellId] | None = None,
    ) -> PublicState:
        source = self._raw_puzzle if raw_puzzle is None else raw_puzzle
        shown_cells = self._revealed if revealed is None else revealed
        cards: list[PublicCard] = []
        for raw_card in source.get("cards", []):
            cid = raw_card["cell"]
            is_rev = cid in shown_cells
            if is_rev:
                clue_raw = raw_card["clue"]
                clue = Clue(id=clue_raw["id"], kind=clue_raw["kind"], data=clue_raw)
                status = Status(raw_card["hidden_status"])
            else:
                clue = None
                status = None
            cards.append(
                PublicCard(
                    cell=cid,
                    name=raw_card["name"],
                    profession=raw_card["profession"],
                    revealed=is_rev,
                    known_status=status,
                    clue=clue,
                )
            )
        return PublicState(
            puzzle_id=source["id"],
            size=int(source["size"]),
            cards=tuple(cards),
        )

    def _serialize_public_state(
        self,
        state: PublicState,
        trace: list[dict[str, Any]],
    ) -> dict[str, Any]:
        names = {c.cell: c.name for c in state.cards}
        serialized_cards: list[dict[str, Any]] = []
        for card in state.cards:
            clue_payload = None
            if card.revealed and card.clue is not None:
                raw_clue = dict(card.clue.data)
                clue_payload = {
                    "id": card.clue.id,
                    "kind": card.clue.kind,
                    "text": format_clue_text(raw_clue, names),
                    "highlighted_cells": extract_referenced_cells(raw_clue, state.size),
                }
            serialized_cards.append({
                "cell": card.cell,
                "name": card.name,
                "profession": card.profession,
                "revealed": card.revealed,
                "known_status": card.known_status.value if card.known_status else None,
                "clue": clue_payload,
            })

        total = len(state.cards)
        revealed_count = sum(1 for c in state.cards if c.revealed)
        return {
            "puzzle_id": state.puzzle_id,
            "size": state.size,
            "revealed_count": revealed_count,
            "total_count": total,
            "solved": revealed_count == total,
            "cards": serialized_cards,
            "trace": list(trace),
        }

    def get_public_state_dict(self) -> dict[str, Any]:
        return self._serialize_public_state(self._build_public_state(), self._deduction_steps)

    def submit_verdict(self, cell: CellId, status_str: str) -> dict[str, Any]:
        status = Status(status_str)
        state = self._build_public_state()
        target_card = next((c for c in state.cards if c.cell == cell), None)
        if target_card is None:
            raise ValueError(f"Unknown cell: {cell}")
        if target_card.revealed:
            return {
                "outcome": VerdictStatus.ACCEPTED.value,
                "newly_revealed": None,
                "message": f"{cell} is already revealed.",
                "state": self.get_public_state_dict(),
            }

        inference = self._oracle.classify_one(state, cell)
        if inference == Inference.INCONSISTENT:
            return {
                "outcome": VerdictStatus.INCONSISTENT.value,
                "newly_revealed": None,
                "message": "Public knowledge base is inconsistent (UNSAT).",
                "state": self.get_public_state_dict(),
            }
        if inference == Inference.UNKNOWN:
            return {
                "outcome": VerdictStatus.NOT_PROVABLE.value,
                "newly_revealed": None,
                "message": f"Not provable yet: neither Criminal nor Innocent is forced for {cell}.",
                "state": self.get_public_state_dict(),
            }
        if inference.value != status.value:
            return {
                "outcome": VerdictStatus.CONTRADICTED.value,
                "newly_revealed": None,
                "message": f"Contradicted: {status.value} for {cell} conflicts with current clues.",
                "state": self.get_public_state_dict(),
            }

        # Accepted & proved: check against hidden truth before revealing
        raw_card = next(c for c in self._raw_puzzle["cards"] if c["cell"] == cell)
        if raw_card["hidden_status"] != status.value:
            return {
                "outcome": VerdictStatus.INCONSISTENT.value,
                "newly_revealed": None,
                "message": f"Puzzle integrity error: proved {status.value} != hidden status.",
                "state": self.get_public_state_dict(),
            }

        self._revealed.add(cell)
        self._step_counter += 1
        active_clues = [c.clue.id for c in state.cards if c.revealed and c.clue is not None]
        self._deduction_steps.append({
            "step": self._step_counter,
            "cell": cell,
            "verdict": status.value,
            "newly_revealed_clue": raw_card["clue"]["id"],
            "active_clues": active_clues,
            "stats": {
                "decisions": 0,
                "propagations": len(active_clues),
                "backtracks": 0,
                "runtime_ms": 0.4,
            },
        })
        return {
            "outcome": VerdictStatus.ACCEPTED.value,
            "newly_revealed": cell,
            "message": f"Accepted! {target_card.name} ({cell}) is {status.value}.",
            "state": self.get_public_state_dict(),
        }

    def get_hint(self) -> dict[str, Any]:
        state = self._build_public_state()
        inferences = self._oracle.classify_all(state)
        for card in state.cards:
            if card.revealed:
                continue
            inf = inferences.get(card.cell, Inference.UNKNOWN)
            if inf in (Inference.CRIMINAL, Inference.INNOCENT):
                # Pick a revealed clue that references this cell if available
                relevant_clue_cell = None
                highlighted: list[CellId] = [card.cell]
                for rev in state.cards:
                    if rev.revealed and rev.clue is not None:
                        refs = extract_referenced_cells(dict(rev.clue.data), state.size)
                        if card.cell in refs:
                            relevant_clue_cell = rev.cell
                            highlighted = refs
                            break
                return {
                    "status": "FOUND",
                    "cell": card.cell,
                    "name": card.name,
                    "suggested_verdict": inf.value,
                    "relevant_clue_cell": relevant_clue_cell,
                    "highlighted_cells": highlighted,
                    "message": (
                        f"Hint: {card.name} ({card.cell}) can be proved as {inf.value}"
                        + (f" using clue at {relevant_clue_cell}." if relevant_clue_cell else ".")
                    ),
                }
            if inf == Inference.INCONSISTENT:
                return {
                    "status": "INCONSISTENT",
                    "cell": None,
                    "suggested_verdict": None,
                    "relevant_clue_cell": None,
                    "highlighted_cells": [],
                    "message": "Knowledge base is inconsistent; no valid hint available.",
                }
        return {
            "status": "NONE",
            "cell": None,
            "suggested_verdict": None,
            "relevant_clue_cell": None,
            "highlighted_cells": [],
            "message": "No forced move found from current public clues.",
        }

    def auto_solve(self) -> dict[str, Any]:
        steps_added: list[dict[str, Any]] = []
        while True:
            state = self._build_public_state()
            inferences = self._oracle.classify_all(state)
            next_cell = None
            next_status = None
            for card in state.cards:
                if card.revealed:
                    continue
                inf = inferences.get(card.cell, Inference.UNKNOWN)
                if inf in (Inference.CRIMINAL, Inference.INNOCENT):
                    next_cell = card.cell
                    next_status = inf.value
                    break
                if inf == Inference.INCONSISTENT:
                    return {
                        "terminal_status": "INCONSISTENT",
                        "steps_added": steps_added,
                        "state": self.get_public_state_dict(),
                    }
            if next_cell is None or next_status is None:
                break
            res = self.submit_verdict(next_cell, next_status)
            if res["outcome"] != VerdictStatus.ACCEPTED.value:
                break
            steps_added.append(self._deduction_steps[-1])

        final_state = self.get_public_state_dict()
        terminal = "SOLVED" if final_state["solved"] else "STUCK"
        return {
            "terminal_status": terminal,
            "steps_added": steps_added,
            "state": final_state,
        }

