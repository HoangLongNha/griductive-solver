# CONTRACTS.md — Griductive Solver v0.1

**Status: proposed contract, requires approval by all five roles at G0 (D1–D2).**
Grounding: CSC14003 AI Project 2, pages 2–8. Technology and interfaces below are team design decisions, not literal API prescriptions from the assignment.

## 0. Architecture / privacy boundary

`GUI -> Controller -> GameSession` and `Controller -> LogicAgent -> CNFEncoder -> DPLL`.
GameSession alone owns the full `Puzzle` and hidden truth/hidden clues. All logic paths receive immutable `PublicState` projections only. No direct `GameSession._puzzle` access outside `game/`.
The Engine's `submit_verdict` delegates logical provability to a `VerdictOracle` injected during construction, operating only on `snapshot()`; revealing a card occurs ONLY after accepted proof and hidden-solution integrity check. A rejected verdict leaves state unchanged.

## 1. Shared data model (`models.py`, VT1)

```python
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Protocol

CellId = str  # e.g. "A1"; row-major A1, B1, C1, A2, ...
Var = int     # 1-based positive variable ID; negative integer = negated literal
Clause = tuple[int, ...]

class Status(str, Enum):
    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"

class VerdictStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    NOT_PROVABLE = "NOT_PROVABLE"
    CONTRADICTED = "CONTRADICTED"
    INCONSISTENT = "INCONSISTENT"

class Inference(str, Enum):
    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"
    UNKNOWN = "UNKNOWN"
    INCONSISTENT = "INCONSISTENT"

@dataclass(frozen=True)
class Region:
    type: Literal["row", "column", "neighbors", "cells"]
    index: int | str | None = None
    cell: CellId | None = None
    cells: tuple[CellId, ...] = ()

@dataclass(frozen=True)
class Clue:
    id: str
    kind: Literal["FACT", "SAME", "DIFFERENT", "EXACTLY", "AT_LEAST", "AT_MOST", "PARITY", "COMPOUND"]
    data: dict  # parse/validate once at load; no NLP

@dataclass(frozen=True)
class PublicCard:
    cell: CellId
    name: str
    profession: str
    revealed: bool
    known_status: Status | None
    clue: Clue | None

@dataclass(frozen=True)
class PublicState:
    puzzle_id: str
    size: int
    cards: tuple[PublicCard, ...]  # row-major

@dataclass(frozen=True)
class CNF:
    clauses: tuple[Clause, ...]
    primary_count: int
    variable_count: int  # includes all auxiliary variables
    # IDs 1..primary_count are primary; aux begin primary_count+1

@dataclass(frozen=True)
class SATStats:
    decisions: int
    propagations: int
    backtracks: int
    runtime_s: float

@dataclass(frozen=True)
class SATResult:
    is_sat: bool
    assignment: dict[int, bool] | None  # COMPLETE 1..variable_count if SAT
    stats: SATStats

@dataclass(frozen=True)
class SubmitResult:
    outcome: VerdictStatus
    state: PublicState
    newly_revealed: CellId | None
    message: str = ""
```

Conventions: `True = Criminal`; `False = Innocent`. Variables map deterministically by row-major board cell, NOT by display name. `CNF` includes auxiliary variables separate from the primary prefix; empty clause means UNSAT and empty conjunction means SAT. Public snapshot is a NEW immutable projection each time; fields `known_status`/`clue` are `None` for face-down cards.

## 2. Game Engine API (VT1)

```python
class VerdictOracle(Protocol):
    def classify_one(self, state: PublicState, cell: CellId) -> Inference: ...

class GameSession:
    def __init__(self, puzzle: "Puzzle", oracle: VerdictOracle): ...
    def snapshot(self) -> PublicState: ...
    def submit_verdict(self, cell: CellId, status: Status) -> SubmitResult: ...
    def restart(self) -> PublicState: ...

def load_puzzle(path: str) -> "Puzzle": ...
```

`load_puzzle`: check JSON Schema + runtime semantic validation from `PUZZLE_SCHEMA.md`. Invalid clue/region -> `PuzzleValidationError`. `GameSession.submit_verdict` snapshots KB, calls oracle, rejects UNKNOWN as NOT_PROVABLE; opposite entailed -> CONTRADICTED; INCONSISTENT -> INCONSISTENT; accepted -> reveal card/status/clue. If a proved claim differs from the hidden solution, raise `PuzzleIntegrityError` without revealing. Never consult hidden truth to decide whether a claim is **provable**. Revealed statuses/clues are always true regardless of the owner's status.

## 3. Logic & CNF encoder (VT2)

```python
def resolve_region(region: Region, size: int) -> tuple[CellId, ...]: ...
def evaluate_clue(clue: Clue, full_assignment: dict[CellId, bool], size: int) -> bool: ...
def encode_kb(public: PublicState) -> CNF: ...
def encode_full_clues(puzzle: "Puzzle") -> CNF: ...  # validation/uniqueness only; NEVER called from agent
```

`encode_kb` reads revealed clues and known statuses ONLY, adds `[v]` or `[-v]` clauses for each known verdict, and allocates auxiliary variables deterministically. Supports 6 core clue types and 2 team-chosen extensions PARITY/COMPOUND. `evaluate_clue` must NOT call `encode_kb`, DPLL or solver. Semantic equivalence: for each primary assignment A, A satisfies clue iff there EXISTS an extension of auxiliary values satisfying encoding.

Recommended direct counting CNF for small regions:
- AT_MOST k: for every (k+1)-subset of region add disjunction of negated variables;
- AT_LEAST k: for every (n-k+1)-subset add disjunction of positive variables;
- EXACTLY k = both.
Boundary cases k=0, k=n, empty clause and no clause must be treated correctly. For larger parity/compound, use correct Tseitin auxiliary variables or direct truth-table exclusion; validate on small boards. Count clauses, primary and auxiliary variables.

## 4. DPLL SAT solver (VT3)

```python
def solve(cnf: CNF, assumptions: tuple[int, ...] = ()) -> SATResult: ...
```

No external SAT solving library for main algorithm. Must perform unit propagation to fixpoint, conflict detection, deterministic variable selection (e.g. smallest unassigned ID), recursive branching, backtracking. Return complete model when SAT, UNSAT otherwise. Count decisions, propagations and backtracks with documented definitions, measure wall clock with `perf_counter()`. Temporary assumptions must not mutate input CNF. If an assumption contradicts another or an existing unit clause => UNSAT.

## 5. Deductive Agent (VT4)

```python
class PublicGamePort(Protocol):
    def snapshot(self) -> PublicState: ...
    def submit_verdict(self, cell: CellId, status: Status) -> SubmitResult: ...

def classify(public: PublicState, encoder, solver) -> dict[CellId, Inference]: ...
def next_forced_verdict(public: PublicState, encoder, solver) -> tuple[CellId, Status] | None: ...
def auto_solve(game: PublicGamePort, encoder, solver) -> "DeductionTrace": ...
def check_unique_complete(puzzle: "Puzzle", encoder, solver) -> bool: ...  # validation scope only
```

First test KB itself for SAT. If KB UNSAT => INCONSISTENT (for every unresolved cell); otherwise for each unresolved `Ci`, test `KB + (-Ci)` and `KB + (Ci)`:
- UNSAT with `-Ci` => CRIMINAL,
- UNSAT with `+Ci` => INNOCENT,
- both SAT => UNKNOWN.
Never reveal UNKNOWN. If >1 forced, choose first row-major. After accepted reveal, rebuild KB and repeat. Stop with SOLVED (all revealed), STUCK (no entailed step) or INCONSISTENT. DeductionTrace step: index, active clue IDs, temporary SAT assumptions/results, verdict, newly revealed clue ID, stats. The full-clue uniqueness check is separate from the public Agent, via an injected validation-only interface; block the first primary assignment with `(-v if true else v)` for each primary variable and test for a second model. Auxiliary variables do NOT appear in the blocking clause.

## 6. GUI & application controller (VT5 + VT1)

```python
class GameView(Protocol):
    def render(self, public: PublicState) -> None: ...
    def highlight_cells(self, cells: tuple[CellId, ...]) -> None: ...
    def show_verdict_result(self, outcome: SubmitResult) -> None: ...
    def show_trace(self, trace: "DeductionTrace") -> None: ...
```

VT5 owns Tkinter/ttk/Canvas only; GUI never reads puzzle source or hidden truths. Controller owns Load, Restart, Hint, Auto Solve, manual verdict dispatch and asynchronous-safe UI updates. Running solver must not block Tkinter's event loop: offload computation, update widgets only on UI thread (Tkinter `.after`). Hint returns at least one currently entailed cell or relevant revealed clue, never a hidden clue.

## 7. Testing, trace and metrics

All tests under `tests/` do not mutate `src` files of another role. Use fake ports with exact signatures before implementations are merged. Standard benchmarks collect `primary_count`, `aux_count`, `clause_count`, `sat_calls`, `decisions`, `propagations`, `backtracks`, `deduction_steps`, `runtime_s`, result/status on same fixed puzzle set. Report failures and timeouts. DPLL per-call metrics must be accumulated by agent benchmark; avoid mixing SAT-call runtime with total app runtime without labels.

## 8. Contract changes and Definition of Done

Only VT1 edits shared models and `CONTRACTS.md`; impacted roles approve contract changes. PR title `feat(module): short description (task-id)`. For task to be Xong: acceptance tests green, independent reviewer approves, PR merged into main, docs/report updated and downstream owners notified. Each role owns its files; shared source changes require owner review.

## 9. Unresolved decisions requiring team approval

- Whether to retain `COMPOUND` extension or choose a different second extension.
- Exact policy for invalid puzzle vs a valid unique but no-next-move puzzle (suggest loader accepts diagnostic fixtures in test-only mode, while playable puzzles require uniqueness and no-guess progression).
- Exact time-limit threshold for stress cases and UI cancellation semantics.
- Whether to preserve deterministic canonical encoding without auxiliary variables for all small cardinalities (suggest yes).
