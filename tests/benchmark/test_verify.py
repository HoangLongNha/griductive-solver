"""Regression checks for benchmark audit accounting (BEN-01..BEN-04)."""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.verify import verify_results


def _write_results(directory, rows, records, metadata=None):
    directory.mkdir()
    with (directory / "summary.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (directory / "audit.json").write_text(
        json.dumps({"metadata": metadata or {}, "records": records}), encoding="utf-8"
    )


def test_verifier_rejects_duplicate_rows_and_missing_run(tmp_path):
    row = {
        "run_index": 1, "puzzle_id": "sample", "category": "3x3", "size": 3,
        "status": "SOLVED", "deduction_steps": 1, "primary_count": 9,
        "aux_count": 0, "clause_count": 1, "sat_calls": 0,
        "recheck_sat_calls": 0, "decisions": 0, "propagations": 0,
        "backtracks": 0, "sat_runtime_s": 0, "uniqueness_sat_calls": 0,
        "uniqueness_decisions": 0, "uniqueness_propagations": 0,
        "uniqueness_backtracks": 0, "is_unique": True, "error": "",
    }
    record = {"run_index": 1, "puzzle_id": "sample", "status": "SOLVED",
              "gameplay_queries": [], "validation_queries": []}
    _write_results(tmp_path / "duplicate", [row, row], [record, record])
    assert any("Duplicate" in error for error in verify_results(tmp_path / "duplicate"))

    _write_results(tmp_path / "missing", [row], [record], {"runs": 2, "dataset_files": ["sample.json"]})
    assert any("Run indexes" in error for error in verify_results(tmp_path / "missing"))


def test_verifier_checks_rechecks_status_and_query_phase(tmp_path):
    row = {
        "run_index": 1, "puzzle_id": "sample", "category": "3x3", "size": 3,
        "status": "TIMEOUT", "deduction_steps": 0, "primary_count": 9,
        "aux_count": 0, "clause_count": 1, "sat_calls": 1,
        "recheck_sat_calls": 2, "decisions": 1, "propagations": 0,
        "backtracks": 0, "sat_runtime_s": 0.001, "uniqueness_sat_calls": 0,
        "uniqueness_decisions": 0, "uniqueness_propagations": 0,
        "uniqueness_backtracks": 0, "is_unique": "N/A", "error": "",
    }
    query = {"purpose": "VERDICT_RECHECK", "decisions": 1,
             "propagations": 0, "backtracks": 0, "runtime_s": 0.001}
    record = {"run_index": 1, "puzzle_id": "sample", "status": "ERROR",
              "gameplay_queries": [query], "validation_queries": []}
    _write_results(tmp_path / "invalid", [row], [record])
    errors = verify_results(tmp_path / "invalid")
    assert any("recheck_sat_calls" in error for error in errors)
    assert any("status differs" in error for error in errors)
    assert any("error detail" in error for error in errors)


def test_verifier_checks_exact_engine_recheck_count(tmp_path):
    row = {
        "run_index": 1, "puzzle_id": "sample", "category": "3x3", "size": 3,
        "status": "SOLVED", "deduction_steps": 1, "primary_count": 9,
        "aux_count": 0, "clause_count": 1, "sat_calls": 1,
        "recheck_sat_calls": 0, "decisions": 0, "propagations": 0,
        "backtracks": 0, "sat_runtime_s": 0, "uniqueness_sat_calls": 0,
        "uniqueness_decisions": 0, "uniqueness_propagations": 0,
        "uniqueness_backtracks": 0, "is_unique": True, "error": "",
    }
    record = {
        "run_index": 1, "puzzle_id": "sample", "status": "SOLVED",
        "gameplay_queries": [{"purpose": "VERDICT_RECHECK", "engine_recheck": True,
                              "decisions": 0, "propagations": 0,
                              "backtracks": 0, "runtime_s": 0}],
        "validation_queries": [],
    }
    _write_results(tmp_path / "recheck", [row], [record])
    assert any("recheck_sat_calls differs" in error for error in verify_results(tmp_path / "recheck"))
