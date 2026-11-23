"""Reproducible DPLL & Agent benchmark runner (Tasks 3.4 & 5.3 / 5.3a)."""
from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = str(ROOT / "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from griductive.agent.entailment import AgentVerdictOracle, classify_kb
from griductive.agent.knowledge_base import QueryPurpose, SATQuery, build_kb, run_sat_query
from griductive.logic import validate_clue
from griductive.logic.encoder import encode_full_clues, encode_kb
from griductive.models import (
    CNF,
    CellId,
    Clue,
    Inference,
    PublicCard,
    PublicState,
    SolverCancelled,
    SolverTimeout,
    Status,
    SubmitResult,
    VerdictOracle,
    VerdictStatus,
    var_to_cell,
)
from griductive.sat.dpll import solve

DEFAULT_PUZZLES_DIR = ROOT / "puzzles"
DEFAULT_OUT_DIR = ROOT / "benchmark" / "results"

SUMMARY_FIELDS = [
    "run_index",
    "puzzle_id",
    "category",
    "size",
    "status",
    "deduction_steps",
    "primary_count",
    "aux_count",
    "clause_count",
    "sat_calls",
    "recheck_sat_calls",
    "decisions",
    "propagations",
    "backtracks",
    "sat_runtime_s",
    "total_runtime_s",
    "uniqueness_sat_calls",
    "uniqueness_decisions",
    "uniqueness_propagations",
    "uniqueness_backtracks",
    "uniqueness_runtime_s",
    "is_unique",
    "error",
]


@dataclass(frozen=True)
class _FallbackCard:
    cell: str
    name: str
    profession: str
    hidden_status: Status
    clue: Clue


@dataclass(frozen=True)
class _FallbackPuzzle:
    id: str
    size: int
    cards: tuple[_FallbackCard, ...]
    initial_revealed: tuple[str, ...]


class _FallbackGameSession:
    """Minimal PublicState-only GameSession shim used only if jsonschema is absent."""

    def __init__(self, puzzle: _FallbackPuzzle, oracle: VerdictOracle) -> None:
        self._puzzle = puzzle
        self._oracle = oracle
        self._revealed = set(puzzle.initial_revealed)

    def snapshot(self) -> PublicState:
        cards = []
        for card in self._puzzle.cards:
            shown = card.cell in self._revealed
            clue = Clue(card.clue.id, card.clue.kind, card.clue.data) if shown else None
            cards.append(
                PublicCard(
                    card.cell,
                    card.name,
                    card.profession,
                    shown,
                    card.hidden_status if shown else None,
                    clue,
                )
            )
        return PublicState(self._puzzle.id, self._puzzle.size, tuple(cards))

    def submit_verdict(self, cell: CellId, status: Status) -> SubmitResult:
        card = next((c for c in self._puzzle.cards if c.cell == cell), None)
        if card is None or cell in self._revealed:
            raise ValueError("Cell is invalid or already revealed")
        state = self.snapshot()
        inference = self._oracle.classify_one(state, cell)
        if inference == Inference.UNKNOWN:
            return SubmitResult(VerdictStatus.NOT_PROVABLE, state, None)
        if inference == Inference.INCONSISTENT:
            return SubmitResult(VerdictStatus.INCONSISTENT, state, None)
        if inference.value != status.value:
            return SubmitResult(VerdictStatus.CONTRADICTED, state, None)
        if card.hidden_status != status:
            raise ValueError("Proved verdict conflicts with hidden solution")
        self._revealed.add(cell)
        return SubmitResult(VerdictStatus.ACCEPTED, self.snapshot(), cell)


def _load_puzzle_with_mode(path: Path, *, diagnostic: bool = False) -> tuple[Any, type, str]:
    """Use the official loader for gameplay; allow false clues in negative benchmarks.

    Diagnostic fixtures still require valid structure and clue references. Their
    intentional contradictions must reach DPLL instead of failing hidden-truth
    validation. This exception is local to the benchmark, never the game loader.
    """
    session_cls = _FallbackGameSession
    mode = "stdlib_fallback_no_jsonschema"
    try:
        from griductive.game.engine import GameSession, load_puzzle
    except ModuleNotFoundError as exc:
        if exc.name != "jsonschema":
            raise
    else:
        if not diagnostic:
            return load_puzzle(str(path)), GameSession, "game_session"
        session_cls = GameSession
        mode = "diagnostic_game_session"

    raw = json.loads(path.read_text(encoding="utf-8"))
    if mode == "diagnostic_game_session":
        from jsonschema import Draft202012Validator

        schema = json.loads((ROOT / "schemas" / "puzzle.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(raw)
    size = int(raw["size"])
    expected = tuple(var_to_cell(v, size) for v in range(1, size * size + 1))
    by_cell = {c["cell"]: c for c in raw["cards"]}
    if len(raw["cards"]) != size * size or set(by_cell) != set(expected):
        raise ValueError("Board must contain each cell exactly once")
    if not set(raw["initial_revealed"]) <= set(expected):
        raise ValueError("Initial reveal outside board")
    cards = tuple(
        _FallbackCard(
            by_cell[cid]["cell"],
            by_cell[cid]["name"],
            by_cell[cid]["profession"],
            Status(by_cell[cid]["hidden_status"]),
            Clue(
                by_cell[cid]["clue"]["id"],
                by_cell[cid]["clue"]["kind"],
                {k: v for k, v in by_cell[cid]["clue"].items() if k not in ("id", "kind")},
            ),
        )
        for cid in expected
    )
    if len({c.name for c in cards}) != len(cards):
        raise ValueError("Duplicate character name")
    if len({c.clue.id for c in cards}) != len(cards):
        raise ValueError("Duplicate clue ID")
    for card in cards:
        validate_clue(card.clue, size)
    puzzle = _FallbackPuzzle(raw["id"], size, cards, tuple(raw["initial_revealed"]))
    return puzzle, session_cls, mode


def discover_puzzles(puzzles_dir: Path, include_negative: bool = False) -> list[tuple[str, Path]]:
    """Return fixed sorted list of (category, path) pairs for benchmarking."""
    categories = ["3x3", "4x4", "5x5"] + (["negative"] if include_negative else [])
    found: list[tuple[str, Path]] = []
    for cat in categories:
        cat_dir = puzzles_dir / cat
        if not cat_dir.is_dir():
            continue
        for path in sorted(cat_dir.glob("*.json")):
            found.append((cat, path))
    return found


def _sum_queries(queries: list[SATQuery]) -> dict[str, Any]:
    return {
        "sat_calls": len(queries),
        "decisions": sum(q.stats.decisions for q in queries),
        "propagations": sum(q.stats.propagations for q in queries),
        "backtracks": sum(q.stats.backtracks for q in queries),
        "sat_runtime_s": round(sum(q.stats.runtime_s for q in queries), 6),
    }


def _serialize_query(q: SATQuery) -> dict[str, Any]:
    return {
        "purpose": q.purpose.value,
        "target_cell": q.target_cell,
        "assumptions": list(q.assumptions),
        "is_sat": q.is_sat,
        "decisions": q.stats.decisions,
        "propagations": q.stats.propagations,
        "backtracks": q.stats.backtracks,
        "runtime_s": q.stats.runtime_s,
    }


def run_single_puzzle(
    path: Path,
    category: str,
    run_index: int,
    timeout_s: float | None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Execute gameplay deduction loop and separate uniqueness validation for one puzzle."""
    gameplay_queries: list[SATQuery] = []
    validation_queries: list[SATQuery] = []
    recheck_sat_calls = 0
    deduction_steps = 0
    primary_count = 0
    aux_count = 0
    clause_count = 0
    status = "ERROR"
    error_msg = ""
    is_unique: str | bool = "N/A"
    puzzle_id = path.stem
    size = 0
    loader_mode = "unknown"

    def timed_solver(cnf: CNF, assumptions: tuple[int, ...] = ()):
        return solve(cnf, assumptions, timeout_s=timeout_s)

    t0 = perf_counter()
    try:
        puzzle, session_cls, loader_mode = _load_puzzle_with_mode(path, diagnostic=category == "negative")
        puzzle_id = puzzle.id
        size = puzzle.size
        oracle = AgentVerdictOracle(encode_kb, timed_solver, query_log=gameplay_queries)
        session = session_cls(puzzle, oracle)

        while True:
            snap = session.snapshot()
            kb = build_kb(snap, encode_kb)
            metrics = kb.metrics
            primary_count = metrics.primary_count
            aux_count = metrics.aux_count
            clause_count = metrics.clause_count

            if not kb.unresolved_cells:
                status = "SOLVED"
                break

            inferences = classify_kb(
                kb,
                timed_solver,
                purpose=QueryPurpose.CLASSIFY,
                query_log=gameplay_queries,
            )
            if any(inf == Inference.INCONSISTENT for inf in inferences.values()):
                status = "INCONSISTENT"
                break

            forced = next(
                (
                    (cell, Status(inferences[cell].value))
                    for cell in kb.unresolved_cells
                    if inferences[cell] in (Inference.CRIMINAL, Inference.INNOCENT)
                ),
                None,
            )
            if forced is None:
                status = "STUCK"
                break

            before_recheck = len(gameplay_queries)
            res = session.submit_verdict(forced[0], forced[1])
            recheck_sat_calls += len(gameplay_queries) - before_recheck
            if res.outcome != VerdictStatus.ACCEPTED:
                status = res.outcome.value
                break
            deduction_steps += 1
    except SolverTimeout as exc:
        status = "TIMEOUT"
        error_msg = str(exc)
    except SolverCancelled as exc:
        status = "CANCELLED"
        error_msg = str(exc)
    except Exception as exc:  # noqa: BLE001
        status = "ERROR"
        error_msg = f"{type(exc).__name__}: {exc}"
    total_runtime_s = round(perf_counter() - t0, 6)

    # Separate validation / uniqueness phase (never mixed into gameplay counters)
    if size > 0 and status != "ERROR":
        try:
            puzzle_val, _, _ = _load_puzzle_with_mode(path, diagnostic=category == "negative")
            full_cnf = encode_full_clues(puzzle_val)
            res1 = run_sat_query(
                timed_solver,
                full_cnf,
                (),
                purpose=QueryPurpose.UNIQUENESS,
                target_cell=None,
                query_log=validation_queries,
            )
            if not res1.is_sat or res1.assignment is None:
                is_unique = False
            else:
                block = tuple(-v if res1.assignment[v] else v for v in range(1, full_cnf.primary_count + 1))
                blocked_cnf = CNF(
                    full_cnf.clauses + (block,),
                    full_cnf.primary_count,
                    full_cnf.variable_count,
                )
                res2 = run_sat_query(
                    timed_solver,
                    blocked_cnf,
                    (),
                    purpose=QueryPurpose.UNIQUENESS,
                    target_cell=None,
                    query_log=validation_queries,
                )
                is_unique = not res2.is_sat
        except (SolverTimeout, SolverCancelled):
            is_unique = "TIMEOUT"
        except Exception:  # noqa: BLE001
            is_unique = "ERROR"

    gp = _sum_queries(gameplay_queries)
    val = _sum_queries(validation_queries)

    row = {
        "run_index": run_index,
        "puzzle_id": puzzle_id,
        "category": category,
        "size": size,
        "status": status,
        "deduction_steps": deduction_steps,
        "primary_count": primary_count,
        "aux_count": aux_count,
        "clause_count": clause_count,
        "sat_calls": gp["sat_calls"],
        "recheck_sat_calls": recheck_sat_calls,
        "decisions": gp["decisions"],
        "propagations": gp["propagations"],
        "backtracks": gp["backtracks"],
        "sat_runtime_s": gp["sat_runtime_s"],
        "total_runtime_s": total_runtime_s,
        "uniqueness_sat_calls": val["sat_calls"],
        "uniqueness_decisions": val["decisions"],
        "uniqueness_propagations": val["propagations"],
        "uniqueness_backtracks": val["backtracks"],
        "uniqueness_runtime_s": val["sat_runtime_s"],
        "is_unique": is_unique,
        "error": error_msg,
    }
    audit_record = {
        "run_index": run_index,
        "puzzle_id": puzzle_id,
        "category": category,
        "status": status,
        "gameplay_queries": [_serialize_query(q) for q in gameplay_queries],
        "validation_queries": [_serialize_query(q) for q in validation_queries],
    }
    return row, audit_record, loader_mode


def _git_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def run_benchmark(
    puzzles_dir: Path = DEFAULT_PUZZLES_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
    runs: int = 3,
    timeout_s: float | None = 10.0,
    include_negative: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run fixed puzzle benchmark across `runs` repetitions and write summary.csv + audit.json."""
    if runs < 1:
        raise ValueError("runs must be >= 1")
    puzzles = discover_puzzles(puzzles_dir, include_negative=include_negative)
    if not puzzles:
        raise FileNotFoundError(f"No benchmark puzzles found in {puzzles_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    audit_records: list[dict[str, Any]] = []
    loader_modes: set[str] = set()

    for run_idx in range(1, runs + 1):
        for category, path in puzzles:
            row, audit_rec, mode = run_single_puzzle(path, category, run_idx, timeout_s)
            rows.append(row)
            audit_records.append(audit_rec)
            loader_modes.add(mode)

    csv_path = out_dir / "summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    audit_payload = {
        "metadata": {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": _git_commit(),
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "loader_modes": sorted(loader_modes),
            "runs": runs,
            "timeout_s": timeout_s,
            "include_negative": include_negative,
            "dataset_files": [p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else str(p) for _, p in puzzles],
        },
        "records": audit_records,
    }
    (out_dir / "audit.json").write_text(json.dumps(audit_payload, indent=2) + "\n", encoding="utf-8")
    return rows, audit_payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run reproducible Griductive solver benchmarks.")
    parser.add_argument("--puzzles-dir", type=Path, default=DEFAULT_PUZZLES_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--include-negative", action="store_true")
    args = parser.parse_args(argv)

    rows, _ = run_benchmark(
        puzzles_dir=args.puzzles_dir,
        out_dir=args.out_dir,
        runs=args.runs,
        timeout_s=args.timeout,
        include_negative=args.include_negative,
    )
    print(f"Benchmark completed: {len(rows)} rows written to {args.out_dir / 'summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
