const { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } = React;

const ASSETS = window.GRIDUCTIVE_ASSETS || { ui: {}, characters: [], environments: {} };

function getInitials(name) {
  return (name || "?")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join("");
}

async function apiFetch(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) {
    const error = new Error(data.error || `HTTP ${res.status}`);
    error.code = data.code;
    throw error;
  }
  return data;
}

function getCharacterAsset(card) {
  const list = ASSETS?.characters || [];
  const byName = list.find(
    (c) => c.name.toLowerCase() === (card.name || "").toLowerCase()
  );
  if (byName && byName.status === "ready" && byName.path) {
    return byName.path;
  }
  return null;
}

function getDispatchThumb(dispatch) {
  const title = dispatch?.title || "";
  if (title.includes("ORACLE") || title.includes("HINT")) {
    return ASSETS.ui?.fortuneTeller?.path;
  }
  if (dispatch?.type === "CONTRADICTED") {
    return ASSETS.characters?.[1]?.path;
  }
  if (dispatch?.type === "NOT_PROVABLE") {
    return ASSETS.ui?.rotaryPhone?.path;
  }
  return ASSETS.characters?.[0]?.path;
}

/* ============================================================
   EVIDENCE CONNECTIONS (SVG STRINGS FROM REAL CLUE TARGETS)
   ============================================================ */
function EvidenceConnections({ containerRef, docRefs, cards, selectedCell, visible }) {
  const [paths, setPaths] = useState([]);
  const [svgSize, setSvgSize] = useState({ w: "100%", h: "100%" });

  const edges = useMemo(() => {
    if (!cards) return [];
    const list = [];
    for (const card of cards) {
      if (!card.revealed || !card.clue?.highlighted_cells) continue;
      for (const target of card.clue.highlighted_cells) {
        if (target === card.cell) continue;
        list.push({
          id: `${card.cell}->${target}`,
          from: card.cell,
          to: target,
        });
      }
    }
    return list;
  }, [cards]);

  const recompute = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;
    setSvgSize({
      w: container.scrollWidth || "100%",
      h: container.scrollHeight || "100%",
    });
    if (edges.length === 0) {
      setPaths([]);
      return;
    }
    const base = container.getBoundingClientRect();
    if (base.width === 0 || base.height === 0) return;
    const scaleX = base.width / (container.clientWidth || 1);
    const scaleY = base.height / (container.clientHeight || 1);

    const next = [];
    for (const edge of edges) {
      const aEl = docRefs.current[edge.from];
      const bEl = docRefs.current[edge.to];
      if (!aEl || !bEl) continue;

      const aRect = aEl.getBoundingClientRect();
      const bRect = bEl.getBoundingClientRect();

      const x1 = (aRect.left - base.left) / scaleX + aEl.offsetWidth * 0.5 + container.scrollLeft;
      const y1 = (aRect.top - base.top) / scaleY + 8 + container.scrollTop;
      const x2 = (bRect.left - base.left) / scaleX + bEl.offsetWidth * 0.5 + container.scrollLeft;
      const y2 = (bRect.top - base.top) / scaleY + 8 + container.scrollTop;

      const dx = Math.abs(x2 - x1);
      const sag = Math.min(34, Math.max(12, dx * 0.12));
      const cx = (x1 + x2) * 0.5;
      const cy = Math.max(y1, y2) + sag;

      next.push({
        ...edge,
        d: `M ${x1.toFixed(1)} ${y1.toFixed(1)} Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${x2.toFixed(1)} ${y2.toFixed(1)}`,
      });
    }
    setPaths(next);
  }, [containerRef, docRefs, edges]);

  useLayoutEffect(() => {
    recompute();
    const container = containerRef.current;
    if (!container) return undefined;

    let ro = null;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(() => recompute());
      ro.observe(container);
    }
    window.addEventListener("resize", recompute);
    return () => {
      if (ro) ro.disconnect();
      window.removeEventListener("resize", recompute);
    };
  }, [recompute, containerRef, visible]);

  return (
    <svg
      className="evidence-strings-svg"
      style={{ width: svgSize.w, height: svgSize.h }}
      aria-hidden="true"
    >
      {paths.map((edge) => {
        const isActive =
          selectedCell && (edge.from === selectedCell || edge.to === selectedCell);
        const isDimmed = selectedCell && !isActive;
        const cls = [
          "evidence-string",
          isActive ? "active" : "",
          isDimmed ? "dimmed" : "",
        ]
          .filter(Boolean)
          .join(" ");
        return <path key={edge.id} d={edge.d} className={cls} />;
      })}
    </svg>
  );
}

/* ============================================================
   PHYSICAL CHARACTER DOCUMENT ON THE BOARD
   ============================================================ */
function CharacterDocument({
  card,
  isSelected,
  isHighlighted,
  isHintTarget,
  busy,
  docRef,
  onSelectDocument,
  onSubmitVerdict,
}) {
  const portraitSrc = card.revealed ? getCharacterAsset(card) : null;
  const classes = [
    "evidence-doc",
    card.revealed ? "revealed" : "sealed",
    isSelected ? "selected" : "",
    isHighlighted ? "clue-target" : "",
    isHintTarget ? "hint-target" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="doc-slot" ref={docRef}>
      <div
        className={classes}
        onClick={() => onSelectDocument(card.cell)}
        role="button"
        tabIndex={0}
        aria-label={`${card.cell} ${card.name} (${card.profession})`}
        onKeyDown={(e) => {
          if (e.target !== e.currentTarget) return;
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelectDocument(card.cell);
          }
        }}
      >
        <img className="doc-pin" src={ASSETS.ui?.pinBrass?.path} alt="" />

        <div>
          <div className="doc-meta-strip">
            <span className="doc-coord">{card.cell}</span>
            {card.revealed ? (
              <span
                className={`doc-stamp ${
                  card.known_status === "CRIMINAL" ? "criminal" : "innocent"
                }`}
              >
                {card.known_status}
              </span>
            ) : (
              <span className="doc-stamp sealed">SEALED</span>
            )}
          </div>

          <div className="doc-photo-frame">
            {card.revealed && portraitSrc ? (
              <img
                src={portraitSrc}
                alt={`${card.name} (${card.profession})`}
                loading="lazy"
              />
            ) : (
              <div className="doc-sealed-cover">
                <span className="doc-sealed-mark">
                  {card.revealed ? getInitials(card.name) : "?"}
                </span>
              </div>
            )}
          </div>

          <div className="doc-hand-name">{card.name}</div>
          <div className="doc-prof">
            {card.profession} · <span>#{card.cell}</span>
          </div>
          <div className="doc-ink-rule" aria-hidden="true">
            <span className="doc-ink-glyph">
              {card.revealed ? (card.known_status === "CRIMINAL" ? "✕" : "✓") : "§"}
            </span>
            <span className="doc-ink-stroke" />
          </div>
        </div>

        {card.revealed && card.clue ? (
          <div className="doc-clue-note">{card.clue.text}</div>
        ) : (
          <div className="doc-actions">
            <button
              type="button"
              className="doc-stamp-btn criminal"
              disabled={busy}
              onClick={(e) => {
                e.stopPropagation();
                onSubmitVerdict(card.cell, "CRIMINAL");
              }}
            >
              CRIMINAL
            </button>
            <button
              type="button"
              className="doc-stamp-btn innocent"
              disabled={busy}
              onClick={(e) => {
                e.stopPropagation();
                onSubmitVerdict(card.cell, "INNOCENT");
              }}
            >
              INNOCENT
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   PHYSICAL CHARACTER DOSSIER (AGED FOLDER SLIDE-OUT)
   ============================================================ */
function CharacterDossier({
  card,
  allCards,
  busy,
  onClose,
  onSelectCell,
  onSubmitVerdict,
}) {
  // Compute real evidence connections involving this character
  const referencingClues = useMemo(() => {
    if (!allCards || !card) return [];
    return allCards.filter(
      (c) =>
        c.revealed &&
        c.clue?.highlighted_cells &&
        c.clue.highlighted_cells.includes(card.cell) &&
        c.cell !== card.cell
    );
  }, [allCards, card?.cell]);

  if (!card) return null;
  const portraitSrc = card.revealed ? getCharacterAsset(card) : null;

  return (
    <aside
      className="dossier-drawer"
      role="dialog"
      aria-label={`Dossier for ${card.name}`}
    >
      <div className="dossier-folder-tab">
        <span className="dossier-folder-label">
          DOSSIER // FILE {card.cell}
        </span>
        <button type="button" className="paper-tab" onClick={onClose}>
          Close Folder
        </button>
      </div>

      <div className="dossier-photo-sheet">
        {card.revealed && portraitSrc ? (
          <img src={portraitSrc} alt={`${card.name} (${card.profession})`} />
        ) : (
          <div className="dossier-photo-placeholder">
            <span className="doc-sealed-mark">
              {card.revealed ? getInitials(card.name) : "?"}
            </span>
          </div>
        )}
        <div>
          <h2 className="dossier-name-hand">{card.name}</h2>
          <div className="doc-prof" style={{ marginTop: 4 }}>
            {card.profession} · Seat {card.cell}
          </div>
          <div style={{ marginTop: 6 }}>
            {card.revealed ? (
              <span
                className={`doc-stamp ${
                  card.known_status === "CRIMINAL" ? "criminal" : "innocent"
                }`}
              >
                {card.known_status}
              </span>
            ) : (
              <span className="doc-stamp sealed">SEALED RECORD</span>
            )}
          </div>
        </div>
      </div>

      <div className="dossier-section">
        <h3>Statement & Evidence</h3>
        {card.revealed && card.clue ? (
          <>
            <p style={{ margin: 0, fontSize: "0.8rem" }}>{card.clue.text}</p>
            {card.clue.highlighted_cells?.length > 0 && (
              <div className="target-chip-row">
                {card.clue.highlighted_cells.map((cid) => (
                  <button
                    key={cid}
                    type="button"
                    className="target-paper-chip"
                    onClick={() => onSelectCell(cid)}
                    style={{ cursor: "pointer" }}
                  >
                    {cid}
                  </button>
                ))}
              </div>
            )}
          </>
        ) : (
          <>
            <p style={{ margin: "0 0 8px", fontSize: "0.78rem", color: "var(--muted-olive)" }}>
              This suspect's file remains sealed. Only a logically entailed verdict will unseal their statement.
            </p>
            <div className="doc-actions">
              <button
                type="button"
                className="doc-stamp-btn criminal"
                disabled={busy}
                onClick={() => onSubmitVerdict(card.cell, "CRIMINAL")}
              >
                STAMP CRIMINAL
              </button>
              <button
                type="button"
                className="doc-stamp-btn innocent"
                disabled={busy}
                onClick={() => onSubmitVerdict(card.cell, "INNOCENT")}
              >
                STAMP INNOCENT
              </button>
            </div>
          </>
        )}
      </div>

      <div className="dossier-section">
        <h3>Referenced By Active Clues</h3>
        {referencingClues.length > 0 ? (
          referencingClues.map((ref) => (
            <div
              key={ref.cell}
              style={{
                fontSize: "0.76rem",
                padding: "5px 0",
                borderBottom: "1px dashed var(--warm-beige)",
              }}
            >
              <strong>
                {ref.name} ({ref.cell}):
              </strong>{" "}
              {ref.clue.text}
            </div>
          ))
        ) : (
          <p style={{ margin: 0, fontSize: "0.76rem", color: "var(--muted-olive)" }}>
            No revealed clues currently point to {card.cell}.
          </p>
        )}
      </div>
    </aside>
  );
}

/* ============================================================
   STATE C — INVESTIGATION BOARD SCENE
   ============================================================ */
function InvestigationBoardScene({
  visible,
  puzzles,
  selectedPuzzleId,
  onChangePuzzleId,
  onLoadPuzzle,
  onRestart,
  onHint,
  onStep,
  onAutoSolve,
  onOpenLedger,
  onStepBack,
  gameState,
  selectedCell,
  highlightedSet,
  hintInfo,
  dispatch,
  onDismissDispatch,
  onSelectDocument,
  onSubmitVerdict,
  busy,
  resetBusy,
}) {
  const surfaceRef = useRef(null);
  const docRefs = useRef({});
  const size = gameState?.size || 3;
  const colLabels = Array.from({ length: size }, (_, i) => String.fromCharCode(65 + i));

  return (
    <section
      className={`investigation-stage ${visible ? "visible" : ""}`}
      aria-hidden={!visible}
      aria-label="Investigation Board"
    >
      <div className="physical-board">
        {/* Contextual Paper Tabs along Wooden Frame */}
        <div className="board-ribbon">
          <div className="board-ribbon-left">
            <button type="button" className="paper-tab" onClick={onStepBack}>
              ← Room View
            </button>

            <select
              className="case-select-note"
              value={selectedPuzzleId}
              disabled={resetBusy}
              aria-label="Select Case File"
              onChange={(e) => onChangePuzzleId(e.target.value)}
            >
              {puzzles.map((p) => (
                <option key={p.id} value={p.id}>
                  [{p.category}] {p.id} ({p.size}x{p.size})
                </option>
              ))}
            </select>

            <button
              type="button"
              className="paper-tab"
              disabled={resetBusy || !selectedPuzzleId}
              onClick={() => onLoadPuzzle(selectedPuzzleId)}
            >
              Open File
            </button>

            <button
              type="button"
              className="paper-tab"
              disabled={resetBusy || !gameState}
              onClick={onRestart}
            >
              Reset Pins
            </button>
          </div>

          <div className="board-ribbon-right">
            <button
              type="button"
              className="paper-tab oracle-tab"
              disabled={busy || !gameState || gameState.solved}
              onClick={onHint}
            >
              <img
                className="oracle-mini-portrait"
                src={ASSETS.ui?.fortuneTeller?.path}
                alt=""
              />
              Oracle Hint
            </button>

            <button
              type="button"
              className="paper-tab primary"
              disabled={busy || !gameState || gameState.solved}
              onClick={onStep}
            >
              Prove One Move
            </button>

            <button
              type="button"
              className="paper-tab primary"
              disabled={busy || !gameState || gameState.solved}
              onClick={onAutoSolve}
            >
              Auto-Deduce
            </button>

            <button type="button" className="paper-tab" onClick={onOpenLedger}>
              Ledger ({gameState?.trace?.length || 0})
            </button>

            {gameState && (
              <span className={`board-tally-slip ${gameState.solved ? "solved" : ""}`}>
                {gameState.revealed_count}/{gameState.total_count}
              </span>
            )}
          </div>
        </div>

        {/* Pinned Documents & SVG Evidence Strings */}
        <div className="board-surface-wrap" ref={surfaceRef}>
          <EvidenceConnections
            containerRef={surfaceRef}
            docRefs={docRefs}
            cards={gameState?.cards}
            selectedCell={selectedCell}
            visible={visible}
          />

          {gameState ? (
            <div
              className="board-documents-grid"
              style={{
                gridTemplateColumns: `24px repeat(${size}, minmax(0, 1fr))`,
              }}
            >
              <div />
              {colLabels.map((col) => (
                <div key={col} className="board-axis-note">
                  {col}
                </div>
              ))}

              {Array.from({ length: size }, (_, r) => {
                const rowNum = r + 1;
                const rowCards = gameState.cards.slice(r * size, (r + 1) * size);
                return (
                  <React.Fragment key={rowNum}>
                    <div className="board-axis-note">{rowNum}</div>
                    {rowCards.map((card) => (
                      <CharacterDocument
                        key={card.cell}
                        card={card}
                        isSelected={selectedCell === card.cell}
                        isHighlighted={highlightedSet.has(card.cell)}
                        isHintTarget={hintInfo?.stage === 2 && hintInfo?.cell === card.cell}
                        busy={busy}
                        docRef={(el) => {
                          if (el) docRefs.current[card.cell] = el;
                          else delete docRefs.current[card.cell];
                        }}
                        onSelectDocument={onSelectDocument}
                        onSubmitVerdict={onSubmitVerdict}
                      />
                    ))}
                  </React.Fragment>
                );
              })}
            </div>
          ) : (
            <p style={{ color: "var(--warm-cream)" }}>Pinning case records...</p>
          )}
        </div>

        {/* Quiet Contextual Pinned Dispatch Note */}
        {dispatch && (
          <div className={`board-dispatch-slip ${dispatch.type}`} role="status">
            <div className="board-dispatch-left">
              <img className="dispatch-thumb" src={getDispatchThumb(dispatch)} alt="" />
              <div>
                <strong>[{dispatch.title}]</strong> {dispatch.message}
              </div>
            </div>
            <button type="button" className="paper-tab" onClick={onDismissDispatch}>
              Acknowledge
            </button>
          </div>
        )}
      </div>
    </section>
  );
}

/* ============================================================
   STATE A & B — DETECTIVE ROOM & CAMERA ZOOM CONTROLLER
   ============================================================ */
function RoomScene({
  viewState,
  gameState,
  onApproachBoard,
  onOpenLedger,
  onConsultOracle,
  onAutoDeduce,
  onLampClick,
  lampFresh,
}) {
  const isRoom = viewState === "ROOM";
  const size = gameState?.size || 3;

  return (
    <>
      <div className={`room-title-slip ${isRoom ? "" : "hidden"}`}>
        <h1>Griductive — Detective's Caseboard</h1>
        <p>
          {gameState
            ? `Case "${gameState.puzzle_id}" · ${gameState.revealed_count}/${gameState.total_count} unsealed · Click the board to examine`
            : "Opening detective's office..."}
        </p>
      </div>

      <div className={`room-canvas ${isRoom ? "" : "focused"}`}>
        <img
          className="env-layer env-background"
          src={ASSETS.environments?.detectiveOffice?.background?.path}
          alt="Detective's office"
        />

        {/* Physical Investigation Board Hotspot aligned with painted wall perspective */}
        <button
          type="button"
          className={`wall-board-hotspot size-${size} ${isRoom ? "" : "dimmed"}`}
          onClick={onApproachBoard}
          aria-label="Examine the investigation board"
        >
          {gameState && (
            <div
              className="wall-board-mini-grid"
              style={{
                gridTemplateColumns: `repeat(${size}, minmax(0, 1fr))`,
                gridTemplateRows: `repeat(${size}, minmax(0, 1fr))`,
              }}
            >
              {gameState.cards.map((card) => {
                const thumb = card.revealed ? getCharacterAsset(card) : null;
                const statusCls = card.revealed
                  ? card.known_status === "CRIMINAL"
                    ? "revealed criminal"
                    : "revealed innocent"
                  : "sealed";
                const stampGlyph = card.revealed
                  ? card.known_status === "CRIMINAL"
                    ? "✕"
                    : "✓"
                  : "?";
                return (
                  <div key={card.cell} className={`mini-pinned-note ${statusCls}`}>
                    <span className="mini-pin-dot" />
                    <div className="mini-note-head">
                      <span className="mini-note-code">{card.cell}</span>
                      <span className="mini-note-glyph">{stampGlyph}</span>
                    </div>
                    <div className="mini-note-body">
                      {card.revealed && thumb ? (
                        <div className="mini-thumb-frame">
                          <img className="mini-thumb" src={thumb} alt="" />
                        </div>
                      ) : (
                        <div className="mini-seal-box">
                          <span className="mini-seal">
                            {card.revealed ? getInitials(card.name) : "?"}
                          </span>
                        </div>
                      )}
                      <div className="mini-note-lines" aria-hidden="true">
                        <span className="mini-note-name">
                          {card.revealed ? card.name.split(" ")[0] : `FILE ${card.cell}`}
                        </span>
                        <span className="mini-ink-bar long" />
                        <span className="mini-ink-bar med" />
                        <span className="mini-ink-bar short">
                          {card.revealed && card.clue ? "→" : "·"}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <span className="board-hover-tag">Approach Investigation Board</span>
        </button>

        <img
          className="env-layer env-midground"
          src={ASSETS.environments?.detectiveOffice?.midground?.path}
          alt=""
        />
        <img
          className="env-layer env-foreground"
          src={ASSETS.environments?.detectiveOffice?.foreground?.path}
          alt=""
        />

        {/* Room Object Hotspots (only interactive in Room View) */}
        {isRoom && (
          <>
            {/* Ceiling lamp = room light switch: turning it off plays the office briefing */}
            <button
              type="button"
              className={`room-hotspot hotspot-lamp ${lampFresh ? "fresh" : ""}`}
              onClick={onLampClick}
              aria-label={
                lampFresh
                  ? "New here? Turn off the ceiling lamp to watch the office briefing"
                  : "Turn off the ceiling lamp to replay the office briefing"
              }
            >
              <span className="lamp-glow" aria-hidden="true" />
              {lampFresh && (
                <span className="lamp-alert" aria-hidden="true">
                  !
                </span>
              )}
              <span className="hotspot-tooltip">Turn off the light · Briefing</span>
            </button>

            <button
              type="button"
              className="room-hotspot hotspot-phone"
              onClick={onConsultOracle}
              aria-label="Consult Fortune Teller on rotary phone"
            >
              <span className="hotspot-tooltip">Ask Oracle Hint</span>
            </button>

            <button
              type="button"
              className="room-hotspot hotspot-typewriter"
              onClick={onOpenLedger}
              aria-label="Open Case Ledger"
            >
              <span className="hotspot-tooltip">Open Case Ledger</span>
            </button>

            <button
              type="button"
              className="room-hotspot hotspot-folder"
              onClick={onApproachBoard}
              aria-label="Open Case Dossier on desk"
            >
              <span className="hotspot-tooltip">Inspect Case Board</span>
            </button>

            <button
              type="button"
              className="room-hotspot hotspot-magnifier"
              onClick={onAutoDeduce}
              aria-label="Run logical deduction with magnifying glass"
            >
              <span className="hotspot-tooltip">Auto-Deduce Case</span>
            </button>
          </>
        )}
      </div>
    </>
  );
}

/* ============================================================
   MAIN APP CONTROLLER (PRESERVES ALL GAME LOGIC & API FLOWS)
   ============================================================ */
/* ============================================================
   CASE BRIEFING — AUTOPLAY ROOM TOUR (FIRST VISIT / REPLAY)
   ============================================================ */
const BRIEFING_SEEN_KEY = "griductive.briefingSeen.v1";

const BRIEFING_TARGETS = {
  lamp: ".hotspot-lamp",
  board: ".wall-board-hotspot",
  folder: ".hotspot-folder",
  phone: ".hotspot-phone",
  magnifier: ".hotspot-magnifier",
  typewriter: ".hotspot-typewriter",
};

// The detective's flashlight is held just behind the viewer, slightly to the right:
// its beam enters from below the bottom edge of the screen (fractions of the viewport).
const BRIEFING_TORCH = { x: 0.62, belowPx: 140 };

// Dwell time per step: about 1.5 s to spot the object plus reading at roughly 5 words/s.
const BRIEFING_STEPS = [
  {
    kicker: "Case briefing",
    title: "Welcome to the office, detective.",
    durationMs: 5000,
    targets: [],
    body: (
      <>
        Every suspect is either <em>Criminal</em> or <em>Innocent</em>. You may stamp a verdict only
        when the revealed statements <b>prove</b> it — never guess. Here is what your office offers.
      </>
    ),
  },
  {
    kicker: "Object 1 of 4",
    title: "The investigation board",
    durationMs: 6000,
    targets: [["board", "Investigation board"], ["folder", "Case file"]],
    body: (
      <>
        Click the <b>board on the wall</b> or the <b>file on your desk</b> to step closer. There you
        pick a case, read statements, and stamp suspects <em>CRIMINAL</em> or <em>INNOCENT</em>.
      </>
    ),
  },
  {
    kicker: "Object 2 of 4",
    title: "The phone — Oracle hint",
    durationMs: 5000,
    targets: [["phone", "Ask the Oracle"]],
    body: (
      <>
        Stuck? Call the Oracle to learn <b>one suspect you can prove right now</b>. Hints use only
        revealed statements and never spoil the answer.
      </>
    ),
  },
  {
    kicker: "Object 3 of 4",
    title: "The magnifier — Auto-deduce",
    durationMs: 4500,
    targets: [["magnifier", "Auto-deduce"]],
    confirm: true,
    body: (
      <>
        Let the detective engine prove one step after another until the <b>case is closed</b>, or
        stop when <b>nothing more can be proven</b>.
      </>
    ),
  },
  {
    kicker: "Object 4 of 4",
    title: "The typewriter — Case ledger",
    durationMs: 4000,
    targets: [["typewriter", "Case ledger"]],
    body: <>Review every proven step: who was unsealed, and which statements proved it.</>,
  },
  {
    kicker: "Recap",
    title: "Your office at a glance",
    durationMs: 5000,
    targets: [
      ["board", "Board"],
      ["folder", "Case file"],
      ["phone", "Hint"],
      ["magnifier", "Auto-deduce"],
      ["typewriter", "Ledger"],
      ["lamp", "Replay briefing"],
    ],
    body: (
      <>
        Everything that was lit can be clicked. Start with the investigation board. To watch this
        briefing again, just switch off the <em>ceiling lamp</em>.
      </>
    ),
  },
];

function readBriefingSeen() {
  try {
    return window.localStorage.getItem(BRIEFING_SEEN_KEY) === "1";
  } catch {
    return false;
  }
}

function markBriefingSeen() {
  try {
    window.localStorage.setItem(BRIEFING_SEEN_KEY, "1");
  } catch {
    /* storage unavailable: the briefing simply plays again next visit */
  }
}

function measureBriefingTargets(targets) {
  return targets
    .map(([name, label]) => {
      const el = document.querySelector(BRIEFING_TARGETS[name]);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { name, label, x: r.left, y: r.top, w: r.width, h: r.height };
    })
    .filter(Boolean);
}

function measureBriefingTorch() {
  return { x: window.innerWidth * BRIEFING_TORCH.x, y: window.innerHeight + BRIEFING_TORCH.belowPx };
}

// Flashlight beam: narrow at the viewer, widening to the size of the lit spot.
function briefingBeamPoints(torch, r) {
  const cx = r.x + r.w / 2;
  const cy = r.y + r.h / 2;
  const dx = cx - torch.x;
  const dy = cy - torch.y;
  const len = Math.hypot(dx, dy) || 1;
  const px = -dy / len;
  const py = dx / len;
  const near = 26;
  const far = (Math.max(r.w, r.h) / 2) * 0.95;
  return [
    [torch.x + px * near, torch.y + py * near],
    [cx + px * far, cy + py * far],
    [cx - px * far, cy - py * far],
    [torch.x - px * near, torch.y - py * near],
  ]
    .map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");
}

// Try spots beside each lit object, then empty corners; keep the one covering the least lit area.
function placeBriefingCard(rects, cw, ch) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const margin = 24;
  const top = 96; // below the title slip
  if (!rects.length) return { x: (vw - cw) / 2, y: (vh - ch) / 2 };
  const clampX = (x) => Math.min(Math.max(x, margin), Math.max(margin, vw - cw - margin));
  const clampY = (y) => Math.min(Math.max(y, top), Math.max(top, vh - ch - margin));
  const spots = [];
  rects.forEach((r) => {
    const cy = r.y + r.h / 2 - ch / 2;
    spots.push(
      [r.x + r.w + 40, cy],
      [r.x - cw - 40, cy],
      [r.x + r.w / 2 - cw / 2, r.y - ch - 56],
      [r.x + r.w / 2 - cw / 2, r.y + r.h + 56],
    );
  });
  spots.push([margin, top + 20], [vw * 0.3 - cw / 2, vh * 0.3], [(vw - cw) / 2, top], [vw - cw - margin, top]);
  const overlap = (x, y) =>
    rects.reduce((sum, r) => {
      const w = Math.min(x + cw, r.x + r.w) - Math.max(x, r.x);
      const h = Math.min(y + ch, r.y + r.h) - Math.max(y, r.y);
      return sum + (w > 0 && h > 0 ? w * h : 0);
    }, 0);
  let best = null;
  for (const [sx, sy] of spots) {
    const x = clampX(sx);
    const y = clampY(sy);
    const o = overlap(x, y);
    if (!best || o < best.o) best = { x, y, o };
    if (o === 0) break;
  }
  return best;
}

const BRIEFING_TWEEN_MS = 700;
const easeInOutCubic = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

// The flashlight spot sweeps from the previously lit objects to the new ones; a spot with
// no predecessor opens up in place (torch switched on), and spots no longer needed fade.
function useBriefingLights(rects, active) {
  const [lights, setLights] = useState([]);
  const shownRef = useRef([]);
  const frameRef = useRef(0);

  useEffect(() => {
    if (active) return undefined;
    cancelAnimationFrame(frameRef.current);
    shownRef.current = [];
    setLights([]);
    return undefined;
  }, [active]);

  useEffect(() => {
    if (!active) return undefined;
    cancelAnimationFrame(frameRef.current);
    const from = shownRef.current.filter((l) => l.o > 0.01);
    const used = new Set();
    const center = (r) => [r.x + r.w / 2, r.y + r.h / 2];
    const tracks = rects.map((to) => {
      let best = -1;
      let bestDist = Infinity;
      from.forEach((f, i) => {
        if (used.has(i)) return;
        const [fx, fy] = center(f);
        const [tx, ty] = center(to);
        const dist = Math.hypot(fx - tx, fy - ty);
        if (dist < bestDist) {
          bestDist = dist;
          best = i;
        }
      });
      if (best >= 0) {
        used.add(best);
        return { from: from[best], to: { ...to, o: 1 } };
      }
      const origin = { x: to.x + to.w * 0.3, y: to.y + to.h * 0.3, w: to.w * 0.4, h: to.h * 0.4 };
      return { from: { ...origin, o: 0 }, to: { ...to, o: 1 } };
    });
    from.forEach((f, i) => {
      if (!used.has(i)) tracks.push({ from: f, to: { ...f, o: 0 } });
    });

    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const start = performance.now();
    const tick = (now) => {
      const t = reduceMotion ? 1 : Math.min(1, (now - start) / BRIEFING_TWEEN_MS);
      const e = easeInOutCubic(t);
      const mix = (a, b) => a + (b - a) * e;
      const frame = tracks.map(({ from: a, to: b }, id) => ({
        id,
        x: mix(a.x, b.x),
        y: mix(a.y, b.y),
        w: mix(a.w, b.w),
        h: mix(a.h, b.h),
        o: mix(a.o ?? 1, b.o),
      }));
      if (t < 1) {
        shownRef.current = frame;
        setLights(frame);
        frameRef.current = requestAnimationFrame(tick);
      } else {
        const settled = frame.filter((l) => l.o > 0.01).map((l, id) => ({ ...l, id }));
        shownRef.current = settled;
        setLights(settled);
      }
    };
    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [rects, active]); // eslint-disable-line react-hooks/exhaustive-deps

  return lights;
}

function RoomBriefing({
  phase,
  endingVariant,
  onSkip,
  onExplore,
  onFinish,
  onLightsOut,
  onEnded,
  onResumeNow,
}) {
  const [step, setStep] = useState(0);
  const [paused, setPaused] = useState(false);
  const [armed, setArmed] = useState(false);
  const [rects, setRects] = useState([]);
  const [torch, setTorch] = useState(null);
  const [cardPos, setCardPos] = useState(null);
  const [resumed, setResumed] = useState(false);
  const cardRef = useRef(null);
  const prevPhaseRef = useRef("OFF");
  const lights = useBriefingLights(rects, phase === "PLAYING" || phase === "EXPLORING");
  const current = BRIEFING_STEPS[step];
  const isLast = step === BRIEFING_STEPS.length - 1;

  const goTo = useCallback(
    (next) => {
      setArmed(false);
      setPaused(false);
      if (next >= BRIEFING_STEPS.length) {
        onFinish();
        return;
      }
      setStep(Math.max(0, next));
    },
    [onFinish],
  );

  useEffect(() => {
    const prev = prevPhaseRef.current;
    if (phase === "LIGHTS_OFF") {
      setStep(0);
      setPaused(false);
      setArmed(false);
    }
    // After the lights go out the room is already dark, so the tour appears at once;
    // coming back from trying an object it fades in instead.
    if (phase === "PLAYING") setResumed(prev === "EXPLORING");
    // Returning from trying an object moves on to the next object.
    if (prev === "EXPLORING" && phase === "PLAYING") goTo(step + 1);
    prevPhaseRef.current = phase;
  }, [phase]); // eslint-disable-line react-hooks/exhaustive-deps

  useLayoutEffect(() => {
    if (phase !== "PLAYING") return undefined;
    const measure = () => {
      const next = measureBriefingTargets(current.targets);
      setRects(next);
      setTorch(measureBriefingTorch());
      const card = cardRef.current;
      if (card) setCardPos(placeBriefingCard(next, card.offsetWidth, card.offsetHeight));
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [phase, step, armed, current]);

  useEffect(() => {
    if (phase !== "PLAYING") return undefined;
    const onKeyDown = (e) => {
      if (e.key === "Escape") onSkip();
      else if (e.key === "ArrowRight") goTo(step + 1);
      else if (e.key === "ArrowLeft") goTo(step - 1);
      else if (e.key === " ") {
        e.preventDefault();
        setPaused((p) => !p);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [phase, step, goTo, onSkip]);

  const handleTargetClick = (name) => {
    if (isLast) {
      onExplore(name, { endBriefing: true });
      return;
    }
    if (current.confirm && !armed) {
      setArmed(true);
      setPaused(true);
      return;
    }
    onExplore(name, { endBriefing: false });
  };

  if (phase === "OFF") return null;

  if (phase === "LIGHTS_OFF") {
    return (
      <div
        className="briefing-layer briefing-lights-off"
        onAnimationEnd={(e) => {
          if (e.target === e.currentTarget) onLightsOut();
        }}
      />
    );
  }

  if (phase === "EXPLORING") {
    return (
      <div className="briefing-paused-chip" role="status">
        <span>Briefing paused — try it out</span>
        <button type="button" className="paper-tab" onClick={onResumeNow}>
          ▶ Resume briefing
        </button>
      </div>
    );
  }

  if (phase === "ENDING") {
    return (
      <div
        className={`briefing-layer briefing-ending ${endingVariant}`}
        onAnimationEnd={(e) => {
          if (e.target === e.currentTarget) onEnded();
        }}
      >
        {endingVariant === "full" && <div className="briefing-ending-stamp">Case open</div>}
      </div>
    );
  }

  // A flashlight lights one spot: draw its beam toward the step's main object only.
  const beam = torch && rects.length > 0 && rects.length <= 2 ? lights[0] : null;
  const pool = (l, scale) => ({ cx: l.x + l.w / 2, cy: l.y + l.h / 2, rx: (l.w / 2) * scale, ry: (l.h / 2) * scale });

  return (
    <div
      className={`briefing-layer ${resumed ? "fade-in" : ""}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="briefing-step-title"
    >
      <svg className="briefing-shade" aria-hidden="true">
        <defs>
          {/* Feathered falloff: clear in the middle of the pool, fading into the dark at the rim.
              The rim fades to transparent (not white) so overlapping spots merge instead of
              one spot's dark rim cutting through its neighbour. */}
          <radialGradient id="briefing-hole">
            <stop offset="0%" stopColor="black" stopOpacity="1" />
            <stop offset="62%" stopColor="black" stopOpacity="1" />
            <stop offset="100%" stopColor="black" stopOpacity="0" />
          </radialGradient>
          {/* Flashlight spot: hot warm-white core, soft falloff */}
          <radialGradient id="briefing-pool">
            <stop offset="0%" stopColor="#fff6e2" stopOpacity="0.42" />
            <stop offset="35%" stopColor="#ffe9c4" stopOpacity="0.22" />
            <stop offset="70%" stopColor="#f6d6a2" stopOpacity="0.07" />
            <stop offset="100%" stopColor="#f6d6a2" stopOpacity="0" />
          </radialGradient>
          {beam && (
            <linearGradient
              id="briefing-beam"
              gradientUnits="userSpaceOnUse"
              x1={torch.x}
              y1={torch.y}
              x2={beam.x + beam.w / 2}
              y2={beam.y + beam.h / 2}
            >
              <stop offset="0%" stopColor="#fff1d6" stopOpacity="0.2" />
              <stop offset="100%" stopColor="#fff1d6" stopOpacity="0.05" />
            </linearGradient>
          )}
          <filter id="briefing-haze" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="16" />
          </filter>
          <mask id="briefing-mask">
            <rect width="100%" height="100%" fill="white" />
            {lights.map((l) => (
              <ellipse key={l.id} {...pool(l, 1.55)} opacity={l.o} fill="url(#briefing-hole)" />
            ))}
          </mask>
        </defs>

        <rect className="briefing-dim" width="100%" height="100%" mask="url(#briefing-mask)" />

        <g className="briefing-light">
          {beam && (
            <polygon
              className="briefing-beam"
              points={briefingBeamPoints(torch, beam)}
              opacity={beam.o}
              fill="url(#briefing-beam)"
              filter="url(#briefing-haze)"
            />
          )}
          {lights.map((l) => (
            <g key={l.id} opacity={l.o}>
              <ellipse className="briefing-pool" {...pool(l, 1.25)} fill="url(#briefing-pool)" />
            </g>
          ))}
        </g>
      </svg>

      {rects.map((r) => {
        const labelBelow = r.y < 90;
        return (
          <React.Fragment key={`${step}-${r.name}`}>
            <button
              type="button"
              className="briefing-hit"
              style={{ left: r.x, top: r.y, width: r.w, height: r.h }}
              onClick={() => handleTargetClick(r.name)}
              aria-label={`Try it: ${r.label}`}
            />
            <div
              className={`briefing-label ${labelBelow ? "below" : ""}`}
              style={{ left: r.x + r.w / 2, top: labelBelow ? r.y + r.h + 14 : r.y - 14 }}
            >
              {r.label}
            </div>
          </React.Fragment>
        );
      })}

      <div
        ref={cardRef}
        className="briefing-card"
        style={cardPos ? { left: cardPos.x, top: cardPos.y } : { visibility: "hidden" }}
      >
        <div className="briefing-progress" aria-hidden="true">
          {BRIEFING_STEPS.map((s, i) => (
            <span key={i} className="briefing-seg">
              {i < step && <span className="briefing-seg-fill done" />}
              {i === step && (
                <span
                  key={`run-${step}`}
                  className={`briefing-seg-fill active ${paused ? "paused" : ""}`}
                  style={{ "--seg-ms": `${s.durationMs}ms` }}
                  onAnimationEnd={() => goTo(step + 1)}
                />
              )}
            </span>
          ))}
        </div>
        <div className="briefing-kicker">
          <span>{current.kicker}</span>
          <button
            type="button"
            className="briefing-pause"
            onClick={() => setPaused((p) => !p)}
            aria-pressed={paused}
            aria-label={paused ? "Play briefing" : "Pause briefing"}
            title={paused ? "Play (Space)" : "Pause (Space)"}
          >
            {paused ? "▶" : "❚❚"}
          </button>
        </div>
        <div key={step} className="briefing-card-content">
          <h2 id="briefing-step-title">{current.title}</h2>
          <p className="briefing-body">{current.body}</p>
          {armed && (
            <p className="briefing-warning">
              Auto-deduce solves the whole case. Click the magnifier again to run it (Reset Pins
              restores the case), or press ▶ to keep watching.
            </p>
          )}
        </div>
        <div className="briefing-footer">
          <span>{current.targets.length > 0 ? "Click anything lit to try it" : ""}</span>
          <button type="button" className="briefing-link" onClick={onSkip}>
            Skip briefing
          </button>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [viewState, setViewState] = useState("ROOM"); // "ROOM" | "TRANSITIONING" | "BOARD"
  const [puzzles, setPuzzles] = useState([]);
  const [selectedPuzzleId, setSelectedPuzzleId] = useState("");
  const [gameState, setGameState] = useState(null);
  const [selectedCell, setSelectedCell] = useState(null);
  const [openDossierCell, setOpenDossierCell] = useState(null);
  const [hintInfo, setHintInfo] = useState(null);
  const [dispatch, setDispatch] = useState(null);
  const [showLedger, setShowLedger] = useState(false);
  const [busy, setBusy] = useState(false);
  const [resetBusy, setResetBusy] = useState(false);
  const [briefingPhase, setBriefingPhase] = useState("OFF"); // OFF | LIGHTS_OFF | PLAYING | EXPLORING | ENDING
  const [briefingSeen, setBriefingSeen] = useState(() => readBriefingSeen());
  const [briefingEnding, setBriefingEnding] = useState("full");
  const requestIdRef = useRef(0);
  const transitionTimerRef = useRef(null);

  useEffect(() => {
    (async () => {
      try {
        const [puzzleRes, stateRes] = await Promise.all([
          apiFetch("/api/puzzles"),
          apiFetch("/api/game/state"),
        ]);
        setPuzzles(puzzleRes.puzzles || []);
        setGameState(stateRes);
        setSelectedPuzzleId(stateRes.puzzle_id);
      } catch (err) {
        setDispatch({ type: "CONTRADICTED", title: "ERROR", message: err.message });
      }
    })();
    return () => {
      if (transitionTimerRef.current) clearTimeout(transitionTimerRef.current);
    };
  }, []);

  const enterBoardView = useCallback(() => {
    if (viewState === "BOARD") return;
    if (transitionTimerRef.current) clearTimeout(transitionTimerRef.current);
    setViewState("TRANSITIONING");
    transitionTimerRef.current = setTimeout(() => {
      setViewState("BOARD");
    }, 520);
  }, [viewState]);

  const returnToRoomView = useCallback(() => {
    if (transitionTimerRef.current) clearTimeout(transitionTimerRef.current);
    setOpenDossierCell(null);
    setViewState("ROOM");
  }, []);

  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key !== "Escape") return;
      if (showLedger) {
        setShowLedger(false);
      } else if (openDossierCell) {
        setOpenDossierCell(null);
      } else if (viewState === "BOARD") {
        returnToRoomView();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [showLedger, openDossierCell, viewState, returnToRoomView]);

  const selectedClueCard = useMemo(() => {
    if (!gameState || !selectedCell) return null;
    return gameState.cards.find((c) => c.cell === selectedCell) || null;
  }, [gameState, selectedCell]);

  const openDossierCard = useMemo(() => {
    if (!gameState || !openDossierCell) return null;
    return gameState.cards.find((c) => c.cell === openDossierCell) || null;
  }, [gameState, openDossierCell]);

  const highlightedSet = useMemo(() => {
    const set = new Set();
    if (hintInfo?.stage === 1 && hintInfo?.supporting_clue_cells?.length) {
      hintInfo.supporting_clue_cells.forEach((cid) => set.add(cid));
    } else if (hintInfo?.stage === 2 && hintInfo?.highlighted_cells) {
      hintInfo.highlighted_cells.forEach((cid) => set.add(cid));
    } else if (selectedClueCard?.revealed && selectedClueCard?.clue?.highlighted_cells) {
      selectedClueCard.clue.highlighted_cells.forEach((cid) => set.add(cid));
    } else if (hintInfo?.highlighted_cells) {
      hintInfo.highlighted_cells.forEach((cid) => set.add(cid));
    }
    return set;
  }, [selectedClueCard, hintInfo]);

  const handleLoadPuzzle = async (puzzleId) => {
    if (!puzzleId) return;
    const requestId = ++requestIdRef.current;
    setBusy(true);
    setResetBusy(true);
    try {
      const state = await apiFetch("/api/game/load", {
        method: "POST",
        body: JSON.stringify({ puzzle_id: puzzleId }),
      });
      if (requestId !== requestIdRef.current) return;
      setGameState(state);
      setSelectedPuzzleId(state.puzzle_id);
      setSelectedCell(null);
      setOpenDossierCell(null);
      setHintInfo(null);
      setDispatch({
        type: "ACCEPTED",
        title: "CASE OPENED",
        message: `Loaded dossier "${state.puzzle_id}" (${state.size}x${state.size}).`,
      });
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setDispatch({ type: "CONTRADICTED", title: "LOAD ERROR", message: err.message });
    } finally {
      if (requestId === requestIdRef.current) {
        setBusy(false);
        setResetBusy(false);
      }
    }
  };

  const handleRestart = async () => {
    const requestId = ++requestIdRef.current;
    setBusy(true);
    setResetBusy(true);
    try {
      const state = await apiFetch("/api/game/restart", { method: "POST" });
      if (requestId !== requestIdRef.current) return;
      setGameState(state);
      setSelectedCell(null);
      setOpenDossierCell(null);
      setHintInfo(null);
      setDispatch({
        type: "NOT_PROVABLE",
        title: "BOARD RESET",
        message: "Returned pinboard to initial revealed clues.",
      });
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setDispatch({ type: "CONTRADICTED", title: err.code || "ERROR", message: err.message });
    } finally {
      if (requestId === requestIdRef.current) {
        setBusy(false);
        setResetBusy(false);
      }
    }
  };

  const handleProofAction = async (path, payload) => {
    const requestId = ++requestIdRef.current;
    setBusy(true);
    try {
      const res = await apiFetch(path, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (requestId !== requestIdRef.current) return;
      setGameState(res.state);
      setHintInfo(null);
      if (res.newly_revealed) {
        setSelectedCell(res.newly_revealed);
      }
      setDispatch({
        type: res.outcome,
        title: res.outcome,
        message: res.message,
      });
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setDispatch({ type: "CONTRADICTED", title: err.code || "ERROR", message: err.message });
    } finally {
      if (requestId === requestIdRef.current) setBusy(false);
    }
  };

  const handleVerdict = (cell, status) => handleProofAction("/api/game/verdict", { cell, status });

  const handleHint = async () => {
    // 2-stage progressive hint: Stage 1 highlights supporting clues; clicking again reveals target cell (Stage 2)
    if (hintInfo && hintInfo.status === "FOUND" && hintInfo.stage === 1) {
      const stage2 = { ...hintInfo, stage: 2 };
      setHintInfo(stage2);
      setSelectedCell(stage2.cell || stage2.relevant_clue_cell || null);
      setDispatch({
        type: "ACCEPTED",
        title: "ORACLE LEAD (2/2)",
        message: stage2.message,
      });
      if (viewState === "ROOM") enterBoardView();
      return;
    }

    const requestId = ++requestIdRef.current;
    setBusy(true);
    try {
      const hint = await apiFetch("/api/game/hint");
      if (requestId !== requestIdRef.current) return;
      const isFound = hint.status === "FOUND";
      const stage1Msg = hint.clue_hint_message
        ? `${hint.clue_hint_message} (Click Oracle Hint again to reveal suspect.)`
        : hint.message;
      const stagedHint = { ...hint, stage: isFound ? 1 : 2 };
      setHintInfo(stagedHint);
      setSelectedCell(hint.relevant_clue_cell || (isFound ? null : hint.cell) || null);
      setDispatch({
        type: hint.status === "INCONSISTENT" ? "CONTRADICTED" : "ACCEPTED",
        title: isFound ? "ORACLE LEAD (1/2)" : hint.status,
        message: isFound ? stage1Msg : hint.message,
      });
      if (viewState === "ROOM") enterBoardView();
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setDispatch({ type: "CONTRADICTED", title: err.code || "ERROR", message: err.message });
    } finally {
      if (requestId === requestIdRef.current) setBusy(false);
    }
  };

  const handleAutoSolve = async () => {
    const requestId = ++requestIdRef.current;
    setBusy(true);
    try {
      const res = await apiFetch("/api/game/auto-solve", { method: "POST" });
      if (requestId !== requestIdRef.current) return;
      setGameState(res.state);
      setHintInfo(null);
      setSelectedCell(null);
      const count = res.steps_added ? res.steps_added.length : 0;
      setDispatch({
        type: res.terminal_status === "SOLVED" ? "ACCEPTED" : "NOT_PROVABLE",
        title: `AUTO-DEDUCE: ${res.terminal_status}`,
        message:
          res.terminal_status === "SOLVED"
            ? `Case closed in ${count} logically entailed step(s).`
            : `Stopped (${res.terminal_status}) after ${count} step(s).`,
      });
      if (viewState === "ROOM") enterBoardView();
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setDispatch({ type: "CONTRADICTED", title: err.code || "ERROR", message: err.message });
    } finally {
      if (requestId === requestIdRef.current) setBusy(false);
    }
  };

  const handleSelectDocument = (cell) => {
    setHintInfo(null);
    setSelectedCell(cell);
    setOpenDossierCell(cell);
  };

  // After trying an object, continue the briefing once the player is back in the office.
  useEffect(() => {
    if (briefingPhase !== "EXPLORING" || viewState !== "ROOM" || showLedger || busy) return undefined;
    const timer = setTimeout(() => setBriefingPhase("PLAYING"), 700);
    return () => clearTimeout(timer);
  }, [briefingPhase, viewState, showLedger, busy]);

  const endBriefing = useCallback((variant) => {
    markBriefingSeen();
    setBriefingSeen(true);
    setBriefingEnding(variant);
    setBriefingPhase("ENDING");
  }, []);
  const finishBriefing = useCallback(() => endBriefing("full"), [endBriefing]);
  const skipBriefing = useCallback(() => endBriefing("quick"), [endBriefing]);

  const exploreFromBriefing = (target, { endBriefing: closeBriefing }) => {
    if (closeBriefing) {
      markBriefingSeen();
      setBriefingSeen(true);
      setBriefingPhase("OFF");
    } else {
      setBriefingPhase("EXPLORING");
    }
    const actions = {
      board: enterBoardView,
      folder: enterBoardView,
      phone: handleHint,
      magnifier: handleAutoSolve,
      typewriter: () => setShowLedger(true),
      lamp: () => setBriefingPhase("LIGHTS_OFF"),
    };
    actions[target]?.();
  };

  const resumeBriefingNow = () => {
    setShowLedger(false);
    returnToRoomView();
  };

  return (
    <div className="game-viewport">
      <RoomScene
        viewState={viewState}
        gameState={gameState}
        onApproachBoard={enterBoardView}
        onOpenLedger={() => setShowLedger(true)}
        onConsultOracle={handleHint}
        onAutoDeduce={handleAutoSolve}
        onLampClick={() => setBriefingPhase("LIGHTS_OFF")}
        lampFresh={!briefingSeen && briefingPhase === "OFF"}
      />


      <RoomBriefing
        phase={briefingPhase}
        endingVariant={briefingEnding}
        onSkip={skipBriefing}
        onExplore={exploreFromBriefing}
        onFinish={finishBriefing}
        onLightsOut={() => setBriefingPhase("PLAYING")}
        onEnded={() => setBriefingPhase("OFF")}
        onResumeNow={resumeBriefingNow}
      />

      <InvestigationBoardScene
        visible={viewState === "BOARD"}
        puzzles={puzzles}
        selectedPuzzleId={selectedPuzzleId}
        onChangePuzzleId={setSelectedPuzzleId}
        onLoadPuzzle={handleLoadPuzzle}
        onRestart={handleRestart}
        onHint={handleHint}
        onStep={() => handleProofAction("/api/game/step", {})}
        onAutoSolve={handleAutoSolve}
        onOpenLedger={() => setShowLedger(true)}
        onStepBack={returnToRoomView}
        gameState={gameState}
        selectedCell={selectedCell}
        highlightedSet={highlightedSet}
        hintInfo={hintInfo}
        dispatch={dispatch}
        onDismissDispatch={() => setDispatch(null)}
        onSelectDocument={handleSelectDocument}
        onSubmitVerdict={handleVerdict}
        busy={busy}
        resetBusy={resetBusy}
      />

      {viewState === "BOARD" && openDossierCard && (
        <CharacterDossier
          card={openDossierCard}
          allCards={gameState?.cards}
          busy={busy}
          onClose={() => setOpenDossierCell(null)}
          onSelectCell={(cid) => {
            setSelectedCell(cid);
            setOpenDossierCell(cid);
          }}
          onSubmitVerdict={handleVerdict}
        />
      )}

      {showLedger && (
        <div className="ledger-backdrop" onClick={() => setShowLedger(false)}>
          <div className="ledger-book" onClick={(e) => e.stopPropagation()}>
            <div className="ledger-header">
              <h2 style={{ margin: 0, fontFamily: "var(--font-serif)" }}>
                Investigation Ledger ({gameState?.trace?.length || 0} steps)
              </h2>
              <button type="button" className="paper-tab" onClick={() => setShowLedger(false)}>
                Close
              </button>
            </div>
            {gameState?.trace?.length ? (
              gameState.trace.map((item) => (
                <div key={item.step} className="ledger-entry">
                  <div>
                    <strong>
                      #{item.step} {item.cell} → {item.verdict}
                    </strong>{" "}
                    (Revealed: {item.newly_revealed_clue})
                  </div>
                  <div style={{ color: "var(--muted-olive)", fontSize: "0.73rem" }}>
                    Active clues: {item.active_clues.join(", ")}
                  </div>
                </div>
              ))
            ) : (
              <p>No verdicts recorded yet.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
