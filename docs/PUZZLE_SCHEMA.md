# Puzzle Schema v1 — draft to ratify at G0

`schemas/puzzle.schema.json` provides structural validation. Runtime `GameEngine.load` MUST also validate semantic constraints:

1. `size=N` yields exactly `N*N` cards, each valid cell exactly once; row-major cell IDs A1, B1, C1, A2… A character has exactly one hidden status and one clue.
2. Names are unique and should appear alphabetically by display name in row-major order. Professions and names are descriptive only unless a clue references its cell identifier.
3. Every clue ID unique; `initial_revealed` nonempty, unique, and references real cells.
4. `FACT` target cell exists. `SAME`/`DIFFERENT` reference two distinct valid cells.
5. `EXACTLY`, `AT_LEAST`, `AT_MOST`: region resolves to unique valid cells, k integer `0 <= k <= len(region)`; reject empty region.
6. Regions: `row` 1..N; `column` A..(A+N-1); `neighbors` includes up to 8 touching horizontally, vertically or diagonally excluding center; `cells` explicit distinct valid cell list.
7. `PARITY`: value ODD or EVEN for number of criminals in region. `COMPOUND`: conjunction of status literals implies another status literal; this is a project-chosen extension (not mandated clue syntax).
8. All clues must evaluate TRUE under the full hidden solution, regardless of criminal/innocent ownership. The full assignment must be unique, and valid evaluation puzzles should allow a no-guess reveal path from initial public knowledge. Keep ambiguous/inconsistent fixtures in `puzzles/negative/` for diagnostic tests only.
9. Never pass `hidden_status` or unrevealed clue through `PublicState`. GUI may show names/professions for all cells, but status/clue fields are null when face-down.
10. A rejected verdict changes neither revealed cards nor the public KB; distinguish NOT_PROVABLE from CONTRADICTED.

## Sample test fixtures

- `tutorial_3x3.json`: 6 required clue types, fixed chain of entailed reveals.
- `extensions_3x3.json`: includes PARITY and COMPOUND.
- `chain_4x4_a.json`, `chain_4x4_b.json`: 4x4 end-to-end cases, intentionally easy baselines.
- `ambiguous_3x3.json`: diagnostic only; no entailed next verdict.
- `inconsistent_public_3x3.json`: diagnostic only; initial public KB UNSAT.

## Limits

JSON Schema alone does not check uniqueness, valid cell coordinates relative to N, clue truth, or solvability; those are semantic validations. Real puzzle generation is **not required** by the PDF; build a stable handcrafted test suite first. Do not call fixtures in `negative/` valid game levels.
