# Final Visual Production Report — Griductive

**Date:** 2026-11-13  
**Status:** Milestones 3–8 complete; raster production, React integration, browser QA, and automated tests passed.

## 1. Locked Visual Direction

- Hand-painted 2D illustrated mystery adventure with matte gouache/watercolor texture and clean `#343333` charcoal contours.
- All raster exports were normalized to the ten-color palette in `ART_BIBLE.md`:
  `#E8DCC3`, `#D3C1A1`, `#B9A58B`, `#A66D53`, `#49352F`, `#39465B`, `#27344C`, `#77775C`, `#343333`, `#E6CFA0`.
- Lighting remains grounded: left-window daylight, restrained warm lamp, and two-to-three value steps.
- No text is baked into raster assets. No neon, bloom, glossy/3D plastic shading, soft airbrush gradients, or ornamental drop shadows were introduced.

## 2. Phase 1 — Prototype Gate

The prototype set was generated and visually inspected against `ART_BIBLE.md` before batch production:

- Alice / Detective: `web/assets/characters/char_01/portrait.webp`
- Bao / Guard: `web/assets/characters/char_02/portrait.webp`
- Detective office base: `web/assets/environments/detective-office/background.webp`
- Rotary telephone prop: `web/assets/ui/rotary-phone.webp`

Gate result: **passed**. Silhouette readability, charcoal line weight, palette, matte surface treatment, and lighting direction were consistent enough for controlled expansion.

## 3. Phase 2 — Character Production

- **25/25** individual character portraits completed at `720×720` with transparent backgrounds.
- Canonical location: `web/assets/characters/{char_id}/portrait.webp`.
- Named puzzle cast: Alice through Phuc (`char_01`–`char_16`).
- Reserved 5×5 cast: Mechanic, Journalist, Botanist, Musician, Tailor, Locksmith, Astronomer, Antique Dealer, and Socialite (`char_17`–`char_25`).
- Fortune Teller Hint avatar completed at `web/assets/ui/fortune-teller/portrait.webp`.
- Faces, viewing directions, age ranges, body language, expressions, occupations, and silhouettes were intentionally varied while preserving a unified drawing system.

## 4. Phases 3–4 — Layered Detective Office

The former single `room_backdrop.svg` dependency was replaced in the active UI by three aligned `1920×1080` WebP layers:

- `web/assets/environments/detective-office/background.webp`
- `web/assets/environments/detective-office/midground.webp`
- `web/assets/environments/detective-office/foreground.webp`

The composition reserves the central deep-blue evidence board for gameplay, keeps daylight on the left, and uses desk, filing cabinets, chairs, paper, magnifier, telephone, lamp, and typewriter to create foreground-to-background depth.

## 5. React Integration and Event Scenes

- `web/asset-manifest.js` now marks all 25 portraits, Fortune Teller, rotary telephone, SVG stamps/pin, and three office layers as `status: "ready"` with canonical paths.
- The React UI loads portraits by character name and preserves concealed-card gameplay with illustrated portraits appearing on reveal.
- The office layers render behind the diegetic caseboard; the previous SVG backdrop is no longer referenced by the active stylesheet.
- The dashboard-like dispatch strip was replaced with full scene presentations:
  - **ACCEPTED:** Alice / warm evidence scene.
  - **CONTRADICTED:** Bao / terracotta refusal scene.
  - **NOT-PROVABLE:** rotary telephone / muted-olive missing-link scene.
  - **ORACLE LEAD:** Fortune Teller / dusty-navy reading-room scene.
- Motion is restrained and functional: paper-settle, portrait-arrival, and scene-rise transforms, with a reduced-motion fallback.
- CSS uses only the locked palette and contains no glow, gradient, `box-shadow`, or non-palette hex colors.

## 6. QA Results

- Browser visual QA passed for the tutorial 3×3 board and production 4×4 board.
- Event scene QA passed for Oracle, Accepted, Contradicted, and Not-Provable states.
- Narrow viewport QA passed with an intentional horizontally scrollable evidence board and stacked event-scene composition.
- Asset inventory: **25** character portraits, **1** Fortune Teller portrait, **1** prop raster, and **3** aligned room layers.
- Automated suite: **23/23 tests passed** via `python -m pytest -q`.

## 7. Production Outcome

The Milestone 3 quota blocker recorded in the earlier report is resolved. Griductive now has a complete, internally consistent raster art set and an asset-driven React presentation ready for further gameplay-only iteration without requiring backend changes.
