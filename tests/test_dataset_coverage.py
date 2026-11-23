"""Dataset structural, semantic, DPLL uniqueness/no-guess, and coverage tests (Tasks 5.3 / 5.3a)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from griductive.agent.entailment import classify_kb
from griductive.agent.knowledge_base import build_kb
from griductive.logic.encoder import encode_full_clues, encode_kb
from griductive.logic.semantics import check_clue, evaluate_clue
from griductive.models import (
    CNF,
    Clue,
    Inference,
    PublicCard,
    PublicState,
    Status,
    cell_to_var,
    var_to_cell,
)
from griductive.sat.dpll import solve

ROOT = Path(__file__).resolve().parents[1]
PUZZLES_DIR = ROOT / "puzzles"

PLAYABLE_FILES = sorted(
    [
        *(PUZZLES_DIR / "3x3").glob("*.json"),
        *(PUZZLES_DIR / "4x4").glob("*.json"),
        *(PUZZLES_DIR / "5x5").glob("*.json"),
    ]
)
NEGATIVE_FILES = sorted((PUZZLES_DIR / "negative").glob("*.json"))
ALL_PUZZLE_FILES = PLAYABLE_FILES + NEGATIVE_FILES

REQUIRED_CLUE_KINDS = {
    "FACT",
    "SAME",
    "DIFFERENT",
    "EXACTLY",
    "AT_LEAST",
    "AT_MOST",
    "PARITY",
    "COMPOUND",
}
REQUIRED_REGION_TYPES = {"row", "column", "neighbors", "cells"}


def _to_clue(raw_clue: dict) -> Clue:
    data = {k: v for k, v in raw_clue.items() if k not in ("id", "kind")}
    return Clue(raw_clue["id"], raw_clue["kind"], data)


def _dpll_full_uniqueness(raw: dict) -> tuple[bool, int]:
    """Return (is_sat, capped_model_count_1_or_2) using production encoder + DPLL."""
    size = raw["size"]

    class _PuzzleProxy:
        def __init__(self) -> None:
            self.size = size
            self.cards = tuple(
                type("CardProxy", (), {"clue": _to_clue(c["clue"])})()
                for c in raw["cards"]
            )

    full_cnf = encode_full_clues(_PuzzleProxy())
    first = solve(full_cnf)
    if not first.is_sat or first.assignment is None:
        return False, 0
    block = tuple(-first.assignment[v] and v or -v for v in range(1, size * size + 1))
    # Blocking clause negates first model's primary assignment: (-v if True else +v).
    block_clause = tuple(-v if first.assignment[v] else v for v in range(1, size * size + 1))
    second_cnf = CNF(
        full_cnf.clauses + (block_clause,),
        full_cnf.primary_count,
        full_cnf.variable_count,
    )
    second = solve(second_cnf)
    return True, (2 if second.is_sat else 1)


def _dpll_no_guess_walk(raw: dict) -> tuple[str, list[str]]:
    """Run row-major forced deduction loop using production KB builder, encoder, and DPLL."""
    size = raw["size"]
    revealed = set(raw["initial_revealed"])
    truth = {c["cell"]: (c["hidden_status"] == "CRIMINAL") for c in raw["cards"]}
    steps: list[str] = []

    while len(revealed) < size * size:
        cards = tuple(
            PublicCard(
                cell=c["cell"],
                name=c["name"],
                profession=c["profession"],
                revealed=(c["cell"] in revealed),
                known_status=Status(c["hidden_status"]) if c["cell"] in revealed else None,
                clue=_to_clue(c["clue"]) if c["cell"] in revealed else None,
            )
            for c in raw["cards"]
        )
        public = PublicState(raw["id"], size, cards)
        kb = build_kb(public, encode_kb)
        inferences = classify_kb(kb, solve)
        if any(inf == Inference.INCONSISTENT for inf in inferences.values()):
            return "INCONSISTENT", steps
        forced_cell = next(
            (cell for cell in kb.unresolved_cells if inferences[cell] in (Inference.CRIMINAL, Inference.INNOCENT)),
            None,
        )
        if forced_cell is None:
            return "STUCK", steps
        predicted_criminal = inferences[forced_cell] == Inference.CRIMINAL
        assert predicted_criminal == truth[forced_cell], f"{raw['id']}: wrong entailment on {forced_cell}"
        revealed.add(forced_cell)
        steps.append(forced_cell)

    return "SOLVED", steps


@pytest.mark.parametrize("path", ALL_PUZZLE_FILES, ids=lambda p: p.relative_to(PUZZLES_DIR).as_posix())
def test_puzzle_semantic_and_clue_truth(path: Path) -> None:
    """Validate structural invariants and clue truth independent of JSON Schema library."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    size = raw["size"]
    assert raw["schema_version"] == 1
    assert size in (3, 4, 5)
    expected_cells = [var_to_cell(v, size) for v in range(1, size * size + 1)]
    assert [c["cell"] for c in raw["cards"]] == expected_cells
    assert len({c["name"] for c in raw["cards"]}) == size * size
    assert len({c["clue"]["id"] for c in raw["cards"]}) == size * size
    assert len(raw["initial_revealed"]) >= 1
    assert set(raw["initial_revealed"]) <= set(expected_cells)
    assert len(set(raw["initial_revealed"])) == len(raw["initial_revealed"])

    assignment = {c["cell"]: (c["hidden_status"] == "CRIMINAL") for c in raw["cards"]}
    all_true = True
    for card in raw["cards"]:
        clue = _to_clue(card["clue"])
        check_clue(clue, size)
        if not evaluate_clue(clue, assignment, size):
            all_true = False
    if path.parent.name == "negative" and "inconsistent" in raw["id"]:
        assert not all_true, f"{raw['id']} should contain an inconsistent/false clue fixture"
    else:
        assert all_true, f"{raw['id']} contains a false clue under hidden_status"


@pytest.mark.parametrize("path", PLAYABLE_FILES, ids=lambda p: p.relative_to(PUZZLES_DIR).as_posix())
def test_playable_puzzle_is_unique_and_no_guess_solvable_via_dpll(path: Path) -> None:
    """DATA-02: Playable 3x3/4x4/5x5 puzzles have unique models and full no-guess paths."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    is_sat, count = _dpll_full_uniqueness(raw)
    assert is_sat and count == 1, f"{raw['id']} full clues must have exact 1 model, got {count}"

    outcome, steps = _dpll_no_guess_walk(raw)
    assert outcome == "SOLVED", f"{raw['id']} stopped with {outcome} after {len(steps)} steps"
    assert len(steps) == raw["size"] ** 2 - len(raw["initial_revealed"])


def test_negative_fixtures_cover_ambiguous_stuck_and_inconsistent() -> None:
    """Task 5.3a: Negative directory exercises ambiguous, mid-game STUCK, and INCONSISTENT."""
    by_id = {json.loads(p.read_text(encoding="utf-8"))["id"]: json.loads(p.read_text(encoding="utf-8")) for p in NEGATIVE_FILES}

    assert _dpll_no_guess_walk(by_id["ambiguous_3x3"]) == ("STUCK", [])
    assert _dpll_no_guess_walk(by_id["inconsistent_public_3x3"]) == ("INCONSISTENT", [])

    stuck_outcome, stuck_steps = _dpll_no_guess_walk(by_id["stuck_4x4"])
    assert stuck_outcome == "STUCK"
    assert len(stuck_steps) >= 2


def test_dataset_coverage_matrix() -> None:
    """Task 5.3 / 5.3a: Dataset covers sizes 3/4/5, all 8 clue kinds, all 4 region types, and 4x4 counting."""
    counts_by_size = {3: 0, 4: 0, 5: 0}
    seen_kinds: set[str] = set()
    seen_regions: set[str] = set()
    four_by_four_non_fact: set[str] = set()
    four_by_four_regions: set[str] = set()

    for path in PLAYABLE_FILES:
        raw = json.loads(path.read_text(encoding="utf-8"))
        size = raw["size"]
        counts_by_size[size] += 1
        for card in raw["cards"]:
            clue = card["clue"]
            seen_kinds.add(clue["kind"])
            if "region" in clue:
                seen_regions.add(clue["region"]["type"])
            if size == 4:
                if clue["kind"] != "FACT":
                    four_by_four_non_fact.add(clue["kind"])
                if "region" in clue:
                    four_by_four_regions.add(clue["region"]["type"])

    assert counts_by_size[3] >= 2
    assert counts_by_size[4] >= 2
    assert counts_by_size[5] >= 1
    assert len(NEGATIVE_FILES) >= 3
    assert seen_kinds == REQUIRED_CLUE_KINDS
    assert seen_regions == REQUIRED_REGION_TYPES
    assert {"EXACTLY", "AT_LEAST", "AT_MOST", "PARITY", "COMPOUND"} <= four_by_four_non_fact
    assert REQUIRED_REGION_TYPES <= four_by_four_regions


def test_all_puzzles_pass_official_loader_and_game_session() -> None:
    """DATA-01: Full jsonschema + semantic validation via GameSession when jsonschema is installed."""
    pytest.importorskip("jsonschema")
    from griductive.agent.entailment import AgentVerdictOracle
    from griductive.game.engine import GameSession, load_puzzle

    for path in PLAYABLE_FILES:
        puzzle = load_puzzle(str(path))
        oracle = AgentVerdictOracle(encode_kb, solve)
        session = GameSession(puzzle, oracle)
        snap = session.snapshot()
        assert len(snap.cards) == puzzle.size * puzzle.size
