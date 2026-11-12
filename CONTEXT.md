# Project Context — Griductive Solver (CSC14003 Project 2)

> Keep this file **concise** and **updated** whenever architecture, APIs, or module status changes.

## 1. Goal & Core Constraints
- **Game:** No-guess Griductive ($N \times N$, $N \in \{3,4,5\}$). Every revealed clue is true; verdicts (`CRIMINAL` / `INNOCENT`) are accepted only when logically entailed by current public knowledge (`KB_t`).
- **Privacy Boundary ([docs/CONTRACTS.md](docs/CONTRACTS.md)):** `GameSession` / `FakeController` owns hidden statuses and unrevealed clues. Only `PublicState` (face-up cards & proved verdicts) is exposed to the Logic Agent and React UI.
- **Tech Stack:** Python 3.13 (stdlib `ThreadingHTTPServer`, `pytest`) + React 18 (zero-build JSX via Babel standalone in `web/`).

## 2. Current Implementation Status
- **Baseline Contracts & Fixtures (Done):**
  - `src/griductive/models.py`: `Status`, `VerdictStatus`, `Inference`, `Region`, `Clue`, `PublicCard`, `PublicState`, `CNF`, `SATResult`, `SubmitResult`, `cell_to_var`, `var_to_cell`.
  - `puzzles/`: `3x3/` (`tutorial_3x3`, `extensions_3x3`), `4x4/` (`chain_4x4_a`, `chain_4x4_b`), `negative/` (`inconsistent_public_3x3`, `ambiguous_3x3`).
- **React UI & Mock Web Backend (Done — Task 5.1 / 5.2, 2D Illustrated Mystery UI):**
  - `main.py`: CLI entry point (`python main.py --open`).
  - `src/griductive/web/server.py`: HTTP server serving `web/` + REST API.
  - `src/griductive/web/fake_controller.py`: `FakeController` + `_MockVerdictOracle` (supports `Load`, `Restart`, `Verdict`, `Hint`, `Auto Solve`, region cell highlighting, and natural-language clue formatting for all 6 core kinds + `PARITY`, `COMPOUND`).
  - `web/index.html`, `web/styles.css`, `web/app.jsx`, `web/asset-manifest.js`: Zero-build React 18 UI using the `Hand-painted 2D Illustrated Mystery Adventure` asset kit (`web/assets/`).
  - Visual assets in `web/assets/`: 3-layer detective office (`detective-office/{background,midground,foreground}.webp`), 25 suspect portraits (`characters/char_01..char_25/portrait.webp`), `fortune-teller/portrait.webp`, `rotary-phone.webp`, and SVG pins/stamps.
- **Pending Production Modules (Assigned to VT1–VT4):**
  - `src/griductive/game/`: Real `GameEngine`, `GameSession`, `loader.py` (Task 1.2).
  - `src/griductive/logic/`: `regions.py`, `semantics.py`, `encoder.py`, `cardinality.py`, `extensions.py` (Tasks 2.1–2.3).
  - `src/griductive/sat/`: `dpll.py`, `statistics.py` (Tasks 3.1–3.2).
  - `src/griductive/agent/`: `knowledge_base.py`, `entailment.py`, `deduction.py`, `trace.py`, `uniqueness.py` (Tasks 4.1–4.3).
  - `src/griductive/controller.py`: Wire real `GameSession` + `LogicAgent` into `web/server.py` replacing `FakeController` (Task 1.3).

## 3. REST API Contract (`src/griductive/web/server.py`)
- `GET /api/puzzles` → `{ puzzles: [{ id, category, size, path }] }`
- `GET /api/game/state` → `PublicState` JSON + `trace`
- `POST /api/game/load` `{ puzzle_id }` → `PublicState` JSON
- `POST /api/game/verdict` `{ cell, status }` → `{ outcome, newly_revealed, message, state }`
- `POST /api/game/restart` → `PublicState` JSON
- `GET /api/game/hint` → `{ status, cell, name, suggested_verdict, relevant_clue_cell, highlighted_cells, message }`
- `POST /api/game/auto-solve` → `{ terminal_status, steps_added, state }`

## 4. Commands
- **Run Web UI:** `python main.py --open` (default `http://127.0.0.1:8000`)
- **Run Tests:** `python -m pytest -q` (currently **23 passed**: 22 fixture tests + 1 web UI/API smoke test in `tests/test_web_ui.py`)

## 5. UI Art Direction & Interaction Flow (Immersive Detective Room + Caseboard)
- **Current delivery scope:** React UI + `web/assets/` artwork wired onto the existing REST API / `FakeController` state contract.
- **Visual Direction:** Hand-painted 2D Illustrated Mystery Adventure — muted vintage storybook palette (`#E8DCC3` warm cream, `#D3C1A1` aged paper, `#B9A58B` warm beige, `#A66D53` muted terracotta, `#49352F` dark walnut, `#39465B` dusty navy, `#27344C` deep blue, `#77775C` muted olive, `#343333` charcoal), serif/typewriter/handwritten typography (`Crimson Pro`, `Courier Prime`, `Caveat`), matte paper & brass-pin textures.
- **Three-State Spatial Flow (`web/app.jsx`, `web/styles.css`):**
  1. **State A — Room View (`RoomScene`):** Layered `1920x1080` detective office (`background`, `midground`, `foreground`) with interactive hotspots on the wall pinboard (`Detective's Caseboard`), rotary phone (`Auto-Deduce`), fortune teller (`Oracle Hint`), and ledger (`Ledger`).
  2. **State B — Board Focus (`TRANSITIONING`):** Smooth CSS camera zoom/translate (`620ms`) anchored to the physical wall pinboard coordinates (`47.29%, 21.11%`).
  3. **State C — Investigation Mode (`InvestigationBoardScene`):** Physical pinboard populated with pinned paper `CharacterDocument` dossiers, physical Criminal/Innocent/Sealed stamps, SVG `EvidenceConnections` strings derived from revealed `clue.highlighted_cells`, contextual dispatch slip, and slide-out aged-folder `CharacterDossier` (`Escape` closes Ledger → Dossier → Room View cleanly while preserving state).
