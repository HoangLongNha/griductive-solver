# Project Audit — Griductive Visual Production

**Date:** 2026-11-13  
**Reference Direction:** `mnt/data/image(7)` (Hand-painted 2D Illustrated Mystery Adventure) & `mnt/data/character design references .jpeg` (Expressive hand-inked character sheet)

---

## 1. Existing Architecture
- **Backend (`src/griductive/`):**
  - `models.py`: Immutable shared contracts (`Status`, `VerdictStatus`, `Inference`, `Region`, `Clue`, `PublicCard`, `PublicState`, `CNF`, `SATResult`, `SubmitResult`). Privacy boundary: face-down cards expose `known_status=None` and `clue=None`.
  - `web/fake_controller.py`: `FakeController` + `_MockVerdictOracle` serving `Load`, `Restart`, `Verdict`, `Hint`, and `Auto Solve` strictly from `PublicState` projections.
  - `web/server.py` & `main.py`: Python 3.13 stdlib `ThreadingHTTPServer` serving static files from `web/` and JSON REST endpoints (`/api/puzzles`, `/api/game/state`, `/api/game/load`, `/api/game/verdict`, `/api/game/restart`, `/api/game/hint`, `/api/game/auto-solve`).
- **Frontend (`web/`):**
  - `web/index.html`, `web/styles.css`, `web/app.jsx`: React 18 + Babel standalone (zero-build JSX, required because `node`/`npm` is not installed in the current environment).
- **Tests (`tests/`):**
  - `test_models.py`, `test_puzzle_fixtures.py`, `test_web_ui.py` (23 passing tests).

---

## 2. Character Inventory (From Actual `puzzles/` Data)
`puzzles/` currently contains 6 JSON files (`3x3/tutorial_3x3.json`, `3x3/extensions_3x3.json`, `4x4/chain_4x4_a.json`, `4x4/chain_4x4_b.json`, `negative/ambiguous_3x3.json`, `negative/inconsistent_public_3x3.json`), defining **16 named characters** (A–P), plus **9 reserved slots (17–25)** for $5 \times 5$ boards:

| Slot | Name | Profession (from JSON) | Source Puzzles |
|---|---|---|---|
| 01 | Alice | Detective | 3x3, 4x4, negative |
| 02 | Bao | Guard | 3x3, 4x4, negative |
| 03 | Chi | Artist | 3x3, 4x4, negative |
| 04 | Dung | Engineer | 3x3, 4x4, negative |
| 05 | Emi | Clerk | 3x3, 4x4, negative |
| 06 | Finn | Doctor | 3x3, 4x4, negative |
| 07 | Gia | Teacher | 3x3, 4x4, negative |
| 08 | Hanh | Farmer | 3x3, 4x4, negative |
| 09 | Ivy | Writer | 3x3, 4x4, negative |
| 10 | Jun | Student | 4x4 |
| 11 | Khai | Pilot | 4x4 |
| 12 | Linh | Chef | 4x4 |
| 13 | Mai | Nurse | 4x4 |
| 14 | Nam | Designer | 4x4 |
| 15 | Oanh | Driver | 4x4 |
| 16 | Phuc | Librarian | 4x4 |
| 17–25 | *(Reserved 5x5)* | Unassigned in `puzzles/` (9 additional slots) | Future 5x5 |
| Hint | *(Oracle)* | Fortune Teller (Hint representative) | UI Control |

---

## 3. Scene & Gameplay Flow Inventory
Griductive is a single-board deduction game with 4 distinct visual/functional states:
1. **Caseboard Investigation Room (Main Scene):** Full-screen detective office (`image(7)`-inspired) housing the $N \times N$ pinned suspect board (`3x3`, `4x4`, `5x5`), desk tools (`Load Case`, `Restart`, `Auto Solve`), and the Fortune Teller Oracle desk figure (`Hint`).
2. **Sealed vs. Revealed Suspect Cards:** Face-down cards show sealed manila/wax dossier backs with `CRIMINAL` / `INNOCENT` stamp actions; revealed cards flip to show the hand-illustrated character portrait, status stamp, and readable clue slip.
3. **Clue Trace & Dossier Overlay:** Selecting a revealed card highlights target coordinates on the pinboard (pinned string/amber markers) and displays the clue's structured breakdown.
4. **Deduction Ledger (Case Log):** Physical notebook/ledger view of proved steps (`#1 B1 -> INNOCENT`, active clues).

---

## 4. Current Asset Inventory & Gaps
- **Existing (`web/assets/`):** Currently holds a previous *Neo-Noir Pixel Art* prototype (`skyline_banner.png`, `card_back.png`, `hint_fortune_teller.png`, `chars/char_01.png`..`char_25.png`), where `char_01..11` were AI-generated pixel art and `char_12..25` were procedural 64x64 pixel placeholders.
- **Gap vs. New Directive:**
  - Style mismatch: Neo-Noir dark pixel art does **not** match `mnt/data/image(7)` (**Hand-painted 2D Illustrated Mystery Adventure**, warm aged paper, muted walnut/navy/terracotta, matte gouache) or `mnt/data/character design references .jpeg` (hand-inked angular storybook/adventure character art).
  - UI architecture mismatch: `web/app.jsx` and `web/styles.css` still use a 2-column dark dashboard layout (`.topbar` + `.board-panel` + `.side-panel` cards) rather than a full-screen diegetic illustrated detective room & physical pinboard.
  - Missing layered environment assets (`background`, `midground`, `foreground`, `lighting`, interactive props, diegetic stamps/folders/notes).

---

## 5. Technical Constraints
1. **No Node.js / npm:** Must run directly via `python main.py` using React 18 + Babel standalone (or vanilla ES modules) and Python stdlib `http.server`.
2. **Image Generation Quota Blocker:** Earlier `image-generator` calls (`gemini-3.1-flash-image`) hit `429 RESOURCE_EXHAUSTED` (reset delay ~4h40m). Phase 1 prototypes must test whether `image-generator` is available; if blocked, report the genuine external blocker clearly rather than fabricating/pretending assets were generated.
3. **Privacy & Gameplay Preservation:** Must preserve all 23 pytest checks and never expose `hidden_status` or unrevealed clues to the frontend.

---

## 6. Proposed Implementation Strategy
1. Author `docs/art-direction/ART_BIBLE.md` (Milestone 2) locking palette, line weight, lighting, and character proportions to `mnt/data/image(7)` and `mnt/data/character design references .jpeg`.
2. Execute Phase 1 Visual Prototypes (Milestone 3) with `image-generator` to validate style alignment.
3. Produce 25 characters + environments + diegetic UI assets sequentially, integrate via a centralized `web/asset-manifest.js`, and replace the dashboard layout with a full-screen diegetic detective office & pinboard.
