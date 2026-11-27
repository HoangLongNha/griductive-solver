"""Tests for benchmark runner, counter accounting, failure retention, and reproducibility (BEN-01..04, DATA-03..04)."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.run import run_benchmark, run_single_puzzle
from benchmark.verify import verify_results

PUZZLES_DIR = ROOT / "puzzles"


def test_inconsistent_fixture_is_only_allowed_in_negative_benchmark() -> None:
    """Keep production validation strict and classify diagnostic KBs using DPLL."""
    path = PUZZLES_DIR / "negative" / "inconsistent_public_3x3.json"
    row, record, _ = run_single_puzzle(path, "3x3", 1, 10.0)
    assert row["status"] == "ERROR"
    assert "PuzzleValidationError" in row["error"]
    assert record["gameplay_queries"] == []

    row, record, mode = run_single_puzzle(path, "negative", 1, 10.0)
    assert row["status"] == "INCONSISTENT"
    assert row["error"] == ""
    assert mode == "diagnostic_game_session"
    assert row["deduction_steps"] == 0
    assert record["gameplay_queries"]
    assert record["gameplay_queries"][0]["is_sat"] is False


@pytest.mark.parametrize("invalid", ["schema", "reference", "duplicate_cell"])
def test_negative_benchmark_still_validates_fixture(tmp_path: Path, invalid: str) -> None:
    raw = json.loads((PUZZLES_DIR / "negative" / "inconsistent_public_3x3.json").read_text(encoding="utf-8"))
    if invalid == "schema":
        del raw["cards"][0]["profession"]
    elif invalid == "reference":
        raw["cards"][0]["clue"]["cell"] = "D1"
    else:
        raw["cards"][1]["cell"] = "A1"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    row, record, _ = run_single_puzzle(path, "negative", 1, 10.0)
    assert row["status"] == "ERROR"
    assert row["error"]
    assert record["gameplay_queries"] == []


def test_benchmark_runner_and_verifier_reproducible_end_to_end(tmp_path: Path) -> None:
    """BEN-01..03, DATA-03: Repeated runs on fixed subset produce identical deterministic counters."""
    subset_dir = tmp_path / "puzzles"
    (subset_dir / "3x3").mkdir(parents=True)
    (subset_dir / "4x4").mkdir(parents=True)
    (subset_dir / "negative").mkdir(parents=True)

    for rel in (
        "3x3/tutorial_3x3.json",
        "3x3/neighbors_cells_3x3.json",
        "4x4/mixed_counting_4x4.json",
        "negative/stuck_4x4.json",
        "negative/inconsistent_public_3x3.json",
    ):
        (subset_dir / rel).write_text((PUZZLES_DIR / rel).read_text(encoding="utf-8"), encoding="utf-8")

    out_dir = tmp_path / "results"
    rows, audit = run_benchmark(
        puzzles_dir=subset_dir,
        out_dir=out_dir,
        runs=2,
        timeout_s=10.0,
        include_negative=True,
    )
    assert len(rows) == 10  # 5 puzzles x 2 runs
    assert "metadata" in audit and len(audit["records"]) == 10

    by_id = {r["puzzle_id"]: r for r in rows}
    assert by_id["tutorial_3x3"]["status"] == "SOLVED"
    assert by_id["tutorial_3x3"]["recheck_sat_calls"] > 0
    assert by_id["mixed_counting_4x4"]["status"] == "SOLVED"
    assert by_id["stuck_4x4"]["status"] == "STUCK"
    assert by_id["stuck_4x4"]["deduction_steps"] == 3
    assert by_id["inconsistent_public_3x3"]["status"] == "INCONSISTENT"

    assert verify_results(out_dir) == []


def test_benchmark_retains_timeout_row_and_verifier_catches_counter_drift(tmp_path: Path) -> None:
    """BEN-01/BEN-04, DATA-04: Timeout emits explicit TIMEOUT row; corrupted counters fail verify."""
    row, rec, _ = run_single_puzzle(
        PUZZLES_DIR / "5x5" / "case_5x5_a.json",
        category="5x5",
        run_index=1,
        timeout_s=0.0,
    )
    assert row["status"] == "TIMEOUT"
    assert row["error"] != ""

    # Write results and confirm verifier accepts preserved TIMEOUT row, then rejects counter drift.
    out_dir = tmp_path / "timeout_res"
    out_dir.mkdir()
    with (out_dir / "summary.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)
    (out_dir / "audit.json").write_text(json.dumps({"metadata": {}, "records": [rec]}), encoding="utf-8")
    assert verify_results(out_dir) == []

    # Corrupt sat_calls in CSV -> BEN-01 must fail verification.
    row_bad = dict(row)
    row_bad["sat_calls"] = int(row["sat_calls"]) + 1
    with (out_dir / "summary.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(row_bad.keys()))
        writer.writeheader()
        writer.writerow(row_bad)
    errors = verify_results(out_dir)
    assert any("BEN-01" in err for err in errors)


def test_timeout_during_recheck_preserves_completed_query(monkeypatch, tmp_path: Path) -> None:
    """A completed recheck query remains counted when the next query times out."""
    import benchmark.run as runner
    from griductive.game.session import GameSession
    from griductive.models import SolverTimeout

    original_submit = GameSession.submit_verdict
    original_solve = runner.solve

    def submit_with_timeout(self, cell, status):
        calls = 0

        def timeout_on_second(cnf, assumptions=(), *, timeout_s=None):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise SolverTimeout("recheck timeout")
            return original_solve(cnf, assumptions, timeout_s=timeout_s)

        with monkeypatch.context() as patch:
            patch.setattr(runner, "solve", timeout_on_second)
            return original_submit(self, cell, status)

    monkeypatch.setattr(GameSession, "submit_verdict", submit_with_timeout)
    row, record, _ = runner.run_single_puzzle(PUZZLES_DIR / "3x3" / "tutorial_3x3.json", "3x3", 1, 10.0)

    assert row["status"] == "TIMEOUT"
    assert row["recheck_sat_calls"] == 1
    marked = [query for query in record["gameplay_queries"] if query["engine_recheck"]]
    assert len(marked) == 1
    out_dir = tmp_path / "results"
    out_dir.mkdir()
    with (out_dir / "summary.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    (out_dir / "audit.json").write_text(json.dumps({"metadata": {}, "records": [record]}), encoding="utf-8")
    assert verify_results(out_dir) == []

    row["recheck_sat_calls"] = 0
    with (out_dir / "summary.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    assert any("recheck_sat_calls" in error for error in verify_results(out_dir))
