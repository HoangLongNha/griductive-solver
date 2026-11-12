# Art Bible — Griductive: Hand-Painted 2D Mystery Adventure

**Primary References:**
- Environment & Lighting: `mnt/data/image(7)` (warm gouache/watercolor detective office, muted paper grain, natural window daylight + soft lamp cone)
- Character Line & Shape Language: `mnt/data/character design references .jpeg` (expressive angular ink contours, matte flat/cel-painted fills, distinct silhouettes)

---

## 1. Visual Identity
**Hand-painted 2D Illustrated Mystery Adventure.** Every character, room layer, prop, and UI document belongs to a single tactile, storybook-detective universe: matte gouache washes, fine organic ink contours, aged paper grain, and grounded architectural perspective.

## 2. Strict Color System
| Token | Hex | Role |
|---|---|---|
| `--cream` | `#E8DCC3` | Primary paper highlights, bright window light, readable card surfaces |
| `--aged-paper` | `#D3C1A1` | Dossier folders, clue slips, secondary paper |
| `--beige` | `#B9A58B` | Plaster walls, worn cardboard, muted warm surfaces |
| `--terracotta` | `#A66D53` | Warm wood accents, brick/leather, `CRIMINAL` muted seal |
| `--walnut` | `#49352F` | Desk, filing cabinets, picture frames, heavy shadows |
| `--dusty-navy` | `#39465B` | Suits, typewriter, pinboard backing, `INNOCENT` muted seal |
| `--deep-blue` | `#27344C` | Pinboard surface, deep shadow washes, evening/indoor depth |
| `--olive` | `#77775C` | Coats, ties, banker accents, foliage/props |
| `--charcoal` | `#343333` | Primary ink linework, typography, dark hardware |
| `--warm-highlight` | `#E6CFA0` | Desk lamp glow, sunlit edges, brass hardware |

**Forbidden:** Neon colors, oversaturation, glossy/plastic 3D shading, cinematic bloom, random hue shifts across assets.

## 3. Texture & Rendering Rules
- Subtle matte paper/canvas grain across backgrounds and documents.
- Visible hand-painted gouache brushwork on walls, wood, and fabrics; clean, slightly tapered charcoal ink outlines (`#343333`) on characters and interactive props.
- Zero photorealism, zero soft airbrush gradients, zero gibberish text inside generated images.

## 4. Lighting System
- **Primary Key Light:** Soft warm daylight entering from left-side shuttered windows (`#E8DCC3` -> `#E6CFA0` wash).
- **Secondary Accent Light:** Focused warm desk lamp & overhead pendant (`#E6CFA0` soft cone, never neon).
- **Shadow Discipline:** Cool-muted navy/walnut shadows (`#27344C` / `#49352F`), consistent left-to-right falloff across all scenes and portraits.

## 5. Perspective & Composition Rules
- **Office / Room Scenes:** Slight 3/4 eye-level architectural perspective with clear **Background** (walls, windows, pinboard), **Midground** (desk, cabinets, bookshelves), and **Foreground** (chair backs, foreground desk edge/props).
- **Portrait Cards:** 3/4 bust framing, eye-line at upper third, consistent scale across all 25 characters.

## 6. Character Illustration Rules (25 Characters + Fortune Teller)
- **Proportions:** Slightly stylized editorial/adventure proportions (head ~1:6.5 to 1:7 of full height; expressive noses, brows, jawlines, and hands).
- **Line & Fill:** Crisp charcoal ink linework (`#343333`) with matte cel/gouache shading (2–3 value steps per surface, no soft airbrush).
- **Silhouette & Identity:** Each of the 25 characters has a unique silhouette (hat, hair, collar, glasses, profession prop) and muted palette derived strictly from Section 2.
- **No Text Artifacts:** Zero embedded names or labels in character artwork.

## 7. Environment & Prop Design
- Every room prop (rotary phone, typewriter, pinned case notes, banker's lamp, filing drawers, wax seal, brass magnifying glass) communicates investigative narrative.
- Interactive props sit on transparent layers or cleanly separated midground/foreground planes for crisp hotspot alignment.

## 8. Diegetic UI Language & Typography
- **No Dashboard Chrome:** No SaaS sidebars, floating glass panels, or rounded admin cards.
- **Physical Metaphor:** The main screen is the Detective's Office; the $N \times N$ grid is a physical **Cork/Navy Pinboard** with pinned manila/cream suspect cards; controls are desk objects (Case Folder selector, Brass Stamp verdicts, Fortune Teller card/figurine for Hint, Mechanical Typewriter/Ledger for Auto Solve & Trace).
- **Typography:** Classic editorial serif (`Georgia` / `Playfair Display` / `Crimson Pro`) for headings & dossier titles; clean humanist/typewriter monospace (`Courier Prime` / `JetBrains Mono`) for coordinates (`A1`–`E5`) and clue text. All text rendered via HTML/CSS, never baked into images.

## 9. Dimensions, Formats & Naming
- **Portraits:** `512x512` (or `600x720` bust) `.webp` (or `.png` fallback), `public/assets/characters/{id}/portrait.webp`.
- **Environments:** `1920x1080` layered `.webp` (`background`, `midground`, `foreground`, `lighting`), `public/assets/environments/{env-id}/`.
- **UI Props/Documents:** Transparent `.webp` / `.svg`, `public/assets/ui/`.
- **Centralized Manifest:** `web/asset-manifest.js` (no hardcoded asset paths inside React components).
