"""Benchmark log accounting and reproducibility verifier (Task 3.4: BEN-01..BEN-04)."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

REPRO_FIELDS = (
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
    "uniqueness_sat_calls",
    "uniqueness_decisions",
    "uniqueness_propagations",
    "uniqueness_backtracks",
    "is_unique",
)


def _sum_audit_queries(queries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "sat_calls": len(queries),
        "decisions": sum(int(q["decisions"]) for q in queries),
        "propagations": sum(int(q["propagations"]) for q in queries),
        "backtracks": sum(int(q["backtracks"]) for q in queries),
        "runtime_s": round(sum(float(q["runtime_s"]) for q in queries), 6),
    }


def verify_results(results_dir: Path) -> list[str]:
    """Return list of verification errors; empty list means all BEN-01..04 checks pass."""
    errors: list[str] = []
    csv_path = results_dir / "summary.csv"
    audit_path = results_dir / "audit.json"

    if not csv_path.is_file():
        return [f"Missing summary.csv at {csv_path}"]
    if not audit_path.is_file():
        return [f"Missing audit.json at {audit_path}"]

    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    records = audit.get("records", [])

    if not rows:
        return ["summary.csv contains 0 rows"]
    if len(rows) != len(records):
        errors.append(f"Row count mismatch: summary.csv={len(rows)} vs audit.json={len(records)}")

    by_key_csv = {(int(r["run_index"]), r["puzzle_id"]): r for r in rows}
    by_key_audit = {(int(rec["run_index"]), rec["puzzle_id"]): rec for rec in records}
    if set(by_key_csv) != set(by_key_audit):
        errors.append("Key mismatch between summary.csv and audit.json (BEN-03)")
        return errors

    # BEN-01 & BEN-02: exact SAT call count and counter sums match audit log
    for key, row in by_key_csv.items():
        rec = by_key_audit[key]
        gp_sum = _sum_audit_queries(rec["gameplay_queries"])
        val_sum = _sum_audit_queries(rec["validation_queries"])

        if int(row["sat_calls"]) != gp_sum["sat_calls"]:
            errors.append(f"{key}: sat_calls {row['sat_calls']} != audit {gp_sum['sat_calls']} (BEN-01)")
        for field in ("decisions", "propagations", "backtracks"):
            if int(row[field]) != gp_sum[field]:
                errors.append(f"{key}: {field} {row[field]} != audit {gp_sum[field]} (BEN-02)")
        if abs(float(row["sat_runtime_s"]) - gp_sum["runtime_s"]) > 1e-4:
            errors.append(f"{key}: sat_runtime_s {row['sat_runtime_s']} != audit {gp_sum['runtime_s']}")

        if int(row["uniqueness_sat_calls"]) != val_sum["sat_calls"]:
            errors.append(f"{key}: uniqueness_sat_calls {row['uniqueness_sat_calls']} != audit {val_sum['sat_calls']}")
        for field in ("decisions", "propagations", "backtracks"):
            csv_field = f"uniqueness_{field}"
            if int(row[csv_field]) != val_sum[field]:
                errors.append(f"{key}: {csv_field} {row[csv_field]} != audit {val_sum[field]}")

    # BEN-03 & BEN-04: fixed puzzle set and reproducible deterministic counters across runs
    runs_map: dict[int, list[dict[str, Any]]] = {}
    for r in rows:
        runs_map.setdefault(int(r["run_index"]), []).append(r)

    sorted_runs = sorted(runs_map)
    baseline_ids = [r["puzzle_id"] for r in runs_map[sorted_runs[0]]]
    baseline_by_id = {r["puzzle_id"]: r for r in runs_map[sorted_runs[0]]}

    for run_idx in sorted_runs[1:]:
        cur_ids = [r["puzzle_id"] for r in runs_map[run_idx]]
        if cur_ids != baseline_ids:
            errors.append(f"Run {run_idx} puzzle order/set differs from run {sorted_runs[0]} (BEN-03)")
            continue
        for r in runs_map[run_idx]:
            base = baseline_by_id[r["puzzle_id"]]
            for field in REPRO_FIELDS:
                if r[field] != base[field]:
                    errors.append(
                        f"Reproducibility drift on {r['puzzle_id']} run {run_idx} field {field}: "
                        f"{r[field]} != {base[field]}"
                    )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Griductive benchmark CSV and audit logs.")
    parser.add_argument("results_dir", type=Path, nargs="?", default=Path("benchmark/results"))
    args = parser.parse_args(argv)

    errors = verify_results(args.results_dir)
    if errors:
        for err in errors:
            print(f"FAIL: {err}")
        return 1
    print(f"OK: verified benchmark results in {args.results_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
