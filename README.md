# Griductive Solver

Play logic puzzles in a React browser UI backed by the Python Game Engine, CNF encoder, DPLL solver and entailment agent. Manual verdicts reveal a card only after a proof; Hint suggests a forced verdict, and Auto-Deduce solves until SOLVED, STUCK or INCONSISTENT without guessing.

## Run

From the repository root, with Python 3.11 or newer:

```powershell
python -m pip install -e '.[dev]'
python main.py --open
```

The default address is http://127.0.0.1:8000. Use `--port 8765` to change it and `--timeout 10` to set the proof time budget per command. The current React page loads React and Babel from a CDN, so browser startup needs internet access.

Choose a case and click **Open File**. Click a face-down card to submit a verdict, **Oracle Hint** for a suggested move, **Prove One Move** for one proof/reveal, or **Auto-Deduce** for the full deduction loop. **Reset Pins** restores the initial board. **Ledger** shows accepted steps. Cases marked `diagnostic` are valid puzzles intended to demonstrate STUCK. Intentionally inconsistent fixture files are rejected by the game loader and remain available to diagnostic tests/benchmarks.

Load and Reset Pins remain available while proofs run. Superseded work cannot overwrite the new board. A proof timeout reports TIMEOUT and preserves the published board and ledger.

## Verify

```powershell
python -m pytest -q
python -m pytest tests/test_full_integration.py -q
python -m benchmark.run --include-negative --runs 2 --out-dir benchmark/results
python -m benchmark.verify benchmark/results
```

Production integration tests exercise real modules through the HTTP API, clue/region coverage, uniqueness, privacy, no-guess terminal states, timeouts and in-flight Load/Restart. Fault injections used for interruptions and inconsistent public input are identified in the tests. The brute-force oracle in `tests/fixture_oracle.py` is test-only.

## Shared interfaces

- `docs/CONTRACTS.md`: interfaces, privacy and HTTP/session semantics.
- `schemas/puzzle.schema.json` and `docs/PUZZLE_SCHEMA.md`: puzzle structure and semantic constraints.
- `docs/TEST_CASE_MATRIX.md`: acceptance cases and integration test mapping.
- `puzzles/`: playable 3×3/4×4/5×5 cases and diagnostic fixtures.
- `main.py`, `web/`, `src/griductive/web/`: React entry point, UI and HTTP adapter.
