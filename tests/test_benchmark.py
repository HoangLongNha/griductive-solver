"""Tests for benchmark runner, counter accounting, failure retention, and reproducibility (BEN-01..04, DATA-03..04)."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.run import run_benchmark, run_single_puzzle
from benchmark.verify import verify_results

PUZZLES_DIR = ROOT / "puzzles"


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
