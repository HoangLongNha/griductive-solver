# Griductive Solver — contract-first starter kit

**Planning + interface package, not a completed solver.** The core DPLL, CNF encoder, agent, game engine and GUI are assigned implementation tasks and must be written by the team. Never use the brute-force oracle in `tests/fixture_oracle.py` as the production SAT solver.

## Files
- `docs/CONTRACTS.md`: shared API and invariants (proposed v0.1)
- `schemas/puzzle.schema.json`: JSON Schema Draft 2020-12
- `docs/PUZZLE_SCHEMA.md`: extra semantic constraints not expressible in schema
- `puzzles/`: 4 valid and 2 intentionally invalid test puzzles
- `tests/test_puzzle_fixtures.py`: independently checks no-guess progression and clue consistency
- `docs/TASKS.md`, `docs/TEST_CASE_MATRIX.md`: 20 planned tasks and acceptance cases

## Verify starter fixtures

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The final project must implement production algorithms itself in Python as required by CSC14003 Project 2. Keep source secrets in GameEngine; never include them in the agent public snapshot.
